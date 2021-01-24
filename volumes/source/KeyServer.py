from flask import Flask, request, jsonify, g
from flask_oidc import OpenIDConnect
import yaml
import requests
import json
import mysql.connector
import hvac
from threading import Thread, Lock
import uuid
import ssl
from poly1305_aes import authenticate, verify
import time
from datetime import datetime
import pickle
import base64
import sys
import logging
import random
import math

local_modules = {}  # lock used with each module
SAE_ID_Addr = {}    # connect SAEs' ID with their IP address
authenticatedHost = {} # authorization list
challenges = {}	# authorization challenges
completedKeys = {} # synchronization list
pref_file = open("/usr/src/app/config/config.yaml", 'r')
prefs = yaml.safe_load(pref_file)

USE_TLS = prefs['global']['tls']['enabled']
verifyCert = prefs['global']['tls']['verify']
clientCert = prefs['global']['tls']['clientCert']
clientKey = prefs['global']['tls']['clientKey']
serverCert = prefs['global']['tls']['serverCert']
serverKey = prefs['global']['tls']['serverCert']


# error codes
SUCCESSFUL = 0
INSUFFICIENT_KEY_AVAILABLE = 1	# (to be used with QKD_GET_KEY)
NO_QKD_CONNECTION_AVAILABLE = 2
HANDLE_IN_USE = 3		# (to be used with QKD_OPEN)
TIMEOUT = 4

app = Flask(__name__)
serverPort = 4000

app.config.update({
	'SECRET_KEY': 'u\x91\xcf\xfa\x0c\xb9\x95\xe3t\xba2K\x7f\xfd\xca\xa3\x9f\x90\x88\xb8\xee\xa4\xd6\xe4',
	'OIDC_CLIENT_SECRETS': '/usr/src/app/src/client_secrets.json',
	'OIDC_VALID_ISSUERS': ['http://' + prefs['keycloak']['address'] + '/auth/realms/quantum_auth'],
	'OIDC_RESOURCE_SERVER_ONLY': 'true'
	})

oidc = OpenIDConnect(app)

# LOG LEVELS
INFO = 0
WARNING = 1
ERROR = 2

# DB ELEMENTS POSITION
# exchangedKeys
KME_ID = 0
KME_IP = 1
KME_PORT = 2
AUTH_KEY_ID = 3
KME_IDs = 4
KEY_COUNT = 5
DEF_KEY_SIZE = 6
MAX_KEY_PER_REQUEST = 8
MAX_KEY_SIZE = 9
MIN_KEY_SIZE = 10
MAX_SAE_ID_COUNT = 11
# KmeExchangerData
KEY_HANDLE = 1
KEY_ID = 2
OPEN = 3
MODULE_ID = 4
TARGET_ADDRESS = 5
# qkdmodule
ID = 0
MODULE = 1
PROTOCOL = 2
MODULE_IP = 3
MAX_KEY_COUNT = 4


def isAuthenticated(token):
	# check if user associated to this token is authorized to perform request
	try:
		auth = authenticatedHost[token['client_id']]
		if str(auth[0]) == str(token['session_state']):
			return auth[1]
		else:
			return False
	except:
		# if client_id key does not exist
		return False

def log(level, message):
	# log only if requested level is enabled globally
	if int(prefs['global']['log_level']) >= level:
		db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
		cursor = db.cursor()
		timestamp = datetime.now()
		cursor.execute("INSERT INTO log (level, message) VALUES ('%d', '%s')" % (level, message))


@app.route('/api/v1/challenges', methods=['GET'])
@oidc.accept_token(True)
def challenge():
	# generate a challenge message
	message = str(datetime.now())
	# save and associate it to SAE client ID
	challenges[g.oidc_token_info['client_id']] = message
	# return challenge
	return json.dumps(message), 200


@app.route('/api/v1/authenticate', methods=['POST'])
@oidc.accept_token(True)
def authenticationReq():
	req_data = json.loads(request.data)
	key_id = req_data['key_id']
	message = req_data['message']
	hmac = eval(req_data['hmac'])
	log(INFO, "Authentication request from " + g.oidc_token_info['client_id'])

	try:
		if message != challenges[g.oidc_token_info['client_id']]:
			# error - kme must authenticate by using a string provided by us
			authenticatedHost[g.oidc_token_info['client_id']] = [g.oidc_token_info['session_state'], False]
			log(WARNING, "Authentication of KME " + g.oidc_token_info['client_id'] + " failed!")

		client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
		client.token = prefs['vault']['token']
		response = client.secrets.kv.read_secret_version(path='storedkeys')
		keys = response['data']['data']['keys']
		key = bytes(keys[key_id], 'utf-8')

		# delete authentication message - if KME needs to authenticate again it will need to request a new challenge message
		del challenges[g.oidc_token_info['client_id']]

		# deserialize hmac
		hmac = base64.b64decode(hmac)
		if verify(hmac, key, message) == True:
			# authorize client to access our rest api
			authenticatedHost[g.oidc_token_info['client_id']] = [g.oidc_token_info['session_state'], True]
			return "OK", 200
		else:
			# authentication failed
			authenticatedHost[g.oidc_token_info['client_id']] = [g.oidc_token_info['session_state'], False]
			log(WARNING, "Authentication of client " + g.oidc_token_info['client_id'] + " failed!")
			return "Unauthorized", 401
	except Exception as e:
		# authentication failed
		authenticatedHost[g.oidc_token_info['client_id']] = [g.oidc_token_info['session_state'], False]
		log(WARNING, "Authentication of client " + g.oidc_token_info['client_id'] + " failed!")
		return "Unauthorized", 401



# NORTHBOUND Interface functions

@app.route('/api/v1/keys/<slave_SAE_ID>/status', methods=['GET'])
@oidc.accept_token(True)
def getStatus(slave_SAE_ID):
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	log(INFO, "Current status requested by client " + g.oidc_token_info['client_id'])
	slave_SAE_ID = str(slave_SAE_ID)
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	# get KME connected to the given SAE
	cursor.execute("SELECT KME_ID FROM destinations WHERE SAE_ID = '%s'" % slave_SAE_ID)
	tKME_ID = cursor.fetchone()
	if tKME_ID is None:
		# destination not known - query all known KME to check if someone konws it
		cursor.execute("SELECT * FROM exchangedKeys")
		kme_list = cursor.fetchall()
		for kme in kme_list:
			if USE_TLS:
				x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
			else:
				x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID)
			if x.status_code == 401:
				# try to authenticate
				if doAuth(kme[KME_ID]) is True:
					# try the request again
					if USE_TLS:
						x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
					else:
						x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID)
			if x.status_code == 200:
				# update destinations
				cursor.execute("INSERT INTO destinations (SAE_ID, KME_ID) VALUES ('%s', '%s')" % (slave_SAE_ID, kme[KME_ID]))
				tKME_ID = kme[KME_ID]
				break
		if tKME_ID is None:
			# requested SAE does not exist in this network - report the error
			log(ERROR, "Status was requested for an unknown destination SAE: " + slave_SAE_ID)
			reply = {"message" : "Bad request format", "details" : [{"SAE_ID error" : "Requested SAE_ID is not known in the network"}]}
			return json.dumps(reply), 400
	# retrieve information to return
	result = {}
	try:
		cursor.execute("SELECT * FROM KmeExchangerData WHERE KME_ID = '%s'" % tKME_ID)
		kmeExc = cursor.fetchall()
		if kmeExc is None or kmeExc == []:
			log(ERROR, "Status request failed because no connection with destination has been established")
			reply = {"message" : "Bad request format", "details" : [{"KME error" : "no connection with destination has been established"}]}
			return json.dumps(reply), 400
		for exchange in kmeExc:
			if exchange[KEY_HANDLE] != None:
				break

		cursor.execute("SELECT * FROM qkdmodules WHERE moduleID = '%s'" % exchange[MODULE_ID])
		module = cursor.fetchone()
		if module is None:
			# error - this is not supposed to happen
			# module does not exist - remove all entries that refer to it
			cursor.execute("DELETE FROM KmeExchangerData WHERE module_ID = '%s'" % exchange[MODULE_ID])
			log(ERROR, "Status request failed because no connection with destination has been established")
			reply = {"message" : "Bad request format", "details" : [{"KME error" : "no connection with destination has been established"}]}
			return json.dumps(reply), 400

		current_module = module[MODULE]
		# get number of available keys
		x = requests.post('http://' + current_module + '/available_keys', data=repr([exchange[KEY_HANDLE]]))
		if x.status_code != 200:
			keysNo = 0
		else:
			keysNo = int(eval(x.content)[0])

		# stored key count
		result['stored_key_count'] = keysNo
		# source KME ID
		result['source_KME_ID'] = prefs['settings']['KME_ID']
		# target KME ID
		result['target_KME_ID'] = tKME_ID
		# master SAE ID
		result['master_SAE_ID'] = request.remote_addr
		# slave SAE ID
		result['slave_SAE_ID'] = slave_SAE_ID
		# key size
		cursor.execute("SELECT * FROM exchangedKeys where KME_ID = '%s'" % tKME_ID)
		data = cursor.fetchone()
		result['key_size'] = data[DEF_KEY_SIZE]
		# max key count
		result['max_key_count'] = module[MAX_KEY_COUNT]
		# max key per request
		# return the lowest value between this KME and the target one
		if int(data[MAX_KEY_PER_REQUEST]) < int(prefs['settings']['MAX_KEY_PER_REQUEST']):
			mkpr = data[MAX_KEY_PER_REQUEST]
		else:
			mkpr = prefs['settings']['MAX_KEY_PER_REQUEST']
		result['max_key_per_request'] = mkpr
		# max key size
		# return the lowest value between this KME and the target one
		if int(data[MAX_KEY_SIZE]) < int(prefs['settings']['MAX_KEY_SIZE']):
			mks = data[MAX_KEY_SIZE]
		else:
			mks = prefs['settings']['MAX_KEY_SIZE']
		result['max_key_size'] = mks
		# min key size
		# return the greatest value between this KME and the target one
		if int(data[MIN_KEY_SIZE]) > int(prefs['settings']['MIN_KEY_SIZE']):
			mks = data[MIN_KEY_SIZE]
		else:
			mks = prefs['settings']['MIN_KEY_SIZE']
		result['min_key_size'] = mks
		# additional SAE count
		result['max_sae_id_count'] = data[MAX_SAE_ID_COUNT]

		# return result in json format as per specifications
		return json.dumps(result)
	except Exception as e:
		# in case of error
		log(ERROR, "Status request failed due to an internal server error")
		reply = {"message" : "Server Error"}
		return json.dumps(reply), 503


@app.route('/api/v1/keys/<slave_SAE_ID>/enc_keys', methods=['POST'])
@oidc.accept_token(True)
def getKey(slave_SAE_ID):
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	log(INFO, "Key requested by client " + g.oidc_token_info['client_id'])
	slave_SAE_ID = str(slave_SAE_ID)
	req_data = json.loads(request.data)
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()

	# get master SAE ID
	masterSAE_ID = req_data['SAE_ID']

	# get KME connected to the slave SAE
	cursor.execute("SELECT KME_ID FROM destinations WHERE SAE_ID = '%s'" % slave_SAE_ID)
	tKME_ID = cursor.fetchone()
	if tKME_ID is None:
		# destination not known - query all known KME to check if someone konws it
		cursor.execute("SELECT * FROM exchangedKeys")
		kme_list = cursor.fetchall()
		for kme in kme_list:
			if USE_TLS:
				x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
			else:
				x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID)
			if x.status_code == 401:
				# try to authenticate
				if doAuth(kme[KME_ID]) is True:
					# try the request again
					if USE_TLS:
						x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
					else:
						x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + slave_SAE_ID)
			if x.status_code == 200:
				# update destinations
				cursor.execute("INSERT INTO destinations (SAE_ID, KME_ID) VALUES ('%s', '%s')" % (slave_SAE_ID, kme[KME_ID]))
				tKME_ID = kme[KME_ID]
				break
		if tKME_ID is None:
			# requested SAE does not exist in this network - report the error
			log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because destination is not known.")
			reply = {"message" : "Bad request format", "details" : [{"SAE_ID error" : "Requested SAE_ID is not known in the network"}]}
			return json.dumps(reply), 400

	# parse parameters
	cursor.execute("SELECT * FROM exchangedKeys WHERE KME_ID = '%s'" % tKME_ID)
	tKME_data = cursor.fetchone()
	if tKME_data is None:
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because of a mismatch in exchangedKeys table: no KME with ID %s was found." % tKME_ID)
		reply = {"message" : "Server Error"}
		return json.dumps(reply), 503
	try:
		keysLen = int(req_data['size'])
	except KeyError:
		# field not specified - use default
		keysLen = prefs['settings']['DEF_KEY_SIZE']
	# key len is requested in bits, our key is an array of bytes, make sure an 8 bit multiple has been requested
	if keysLen % 8 != 0:
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because wrong key size was requested (not an 8 bits multiple).")
		reply = {"message" : "Bad request format", "details" : [{"Keys size error" : "Key size must be a multiple of 8 bits"}]}
		return json.dumps(reply), 400
	# express keyLen in bytes
	keysLen = int(keysLen / 8)

	try:
		keysNo = int(req_data['number'])
	except KeyError:
		# field not specified - use default
		keysNo = 1
	if tKME_data[MAX_KEY_PER_REQUEST] > prefs['settings']['MAX_KEY_PER_REQUEST']:
		maxKeyPR = prefs['settings']['MAX_KEY_PER_REQUEST']
	else:
		maxKeyPR = tKME_data[MAX_KEY_PER_REQUEST]
	if keysNo > maxKeyPR:
		cursor.execute("UNLOCK TABLES")
		# SAE is requesting more keys than available - reply with an error
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because client requested more keys than available.")
		reply = {"message" : "Bad request format", "details" : [{"Keys number error" : "Requested more keys than allowed - please check status to know the maximum keys per request number allowed"}]}
		return json.dumps(reply), 400

	additionalIDs = None
	try:
		additionalIDs = req_data['additional_slave_SAE_IDs']
	except KeyError:
		# field not specified
		pass
	if additionalIDs is not None:
		# check that target KME supports additional slave SAE IDs
		additionalIDsCount = len(additionalIDs)
		if additionalIDsCount > tKME_data[MAX_SAE_ID_COUNT]:
			cursor.execute("UNLOCK TABLES")
			# target KME does not support required number of additional slave SAE - reply with an error
			log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because target KME does not support required number of additional slave SAE.")
			reply = {"message" : "Bad request format", "details" : [{"Additional_slave_SAE_IDs error" : "Target KME does not support required number of additional slave SAE - please check status to know the number of additional SAE supported for selected destination"}]}
			return json.dumps(reply), 400
	try:
		extensionMandatory = req_data['extension_mandatory']
		if extensionMandatory is not None:
			cursor.execute("UNLOCK TABLES")
			# extension are currently not supported - report an error
			log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because required mandatory extensions are not supported.")
			reply = {"message" : "not all extension_mandatory parameters are supported", "details" : []}
			for ext in extensionMandatory:
				for k in ext.keys():
					reply["details"].append({"extension_mandatory_unsupported" : k})
			return json.dumps(reply), 400
	except KeyError:
		# field not specified
		pass
	# ignore extension_optional


	# retrieve requested key(s)
	cursor.execute("SELECT * FROM KmeExchangerData WHERE KME_ID = '%s'" % tKME_ID)
	result = cursor.fetchall()
	if result is None or result == []:
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because no connection with destination has been established.")
		reply = {"message" : "Bad request format", "details" : [{"KME error" : "no connection with destination has been established"}]}
		return json.dumps(reply), 400
	for exchange in result:
		if exchange[KEY_HANDLE] != None:
			break

	keyID = exchange[KEY_ID]
	cursor.execute("SELECT * FROM qkdmodules WHERE moduleID = '%s'" % exchange[MODULE_ID])
	module = cursor.fetchone()
	if module is None:
		# error - this is not supposed to happen
		# module does not exist - remove all entries that refer to it
		cursor.execute("DELETE FROM KmeExchangerData WHERE module_ID = '%s'" % exchange[MODULE_ID])
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because no connection with destination has been established.")
		reply = {"message" : "Bad request format", "details" : [{"KME error" : "no connection with destination has been established"}]}
		return json.dumps(reply), 400

	# keys are exchanged in chunks of 128 bits (16 bytes), check the number of chunks requested to meet key length specification
	requiredKeys = math.ceil(keysLen / 16)
	current_module = module[MODULE]
	kidlist = []
	kcollection = []
	# check that available keys are enough
	x = requests.post('http://' + current_module + '/available_keys', data=repr([exchange[KEY_HANDLE]]))
	if x.status_code != 200:
		availKeys = 0
	else:
		availKeys = int(eval(x.content)[0])
	app.logger.info("result: %s - content: %s" % (str(availKeys), str(x.content))) # [cr] remove
	if (keysNo*requiredKeys) > availKeys:
		cursor.execute("UNLOCK TABLES")
		# SAE is requesting more keys than available - reply with an error
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because client requested more keys than available.")
		reply = {"message" : "Bad request format", "details" : [{"Keys number error" : "Requested more keys than available - please check status to know the currently available keys number"}]}
		return json.dumps(reply), 400
	for j in range(keysNo):
		index = 0
		key = bytearray()
		for i in range(requiredKeys):
			x = requests.post('http://' + current_module + '/get_key', data=repr([exchange[KEY_HANDLE], -1, None]))
			if x.status_code != 200:
				log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because no key is available.")
				reply = {"message" : "Bad request format", "details" : [{"QKD error" : "no key is available"}]}
				return json.dumps(reply), 400
			else:
				chunk, midIndex, status = eval(x.content)
			key = key + chunk
			# save the first index
			if i == 0:
				index = midIndex
		# make sure key has the right size
		key = key[:keysLen]
		# encode it to base64 as per QKD specifications (ETSI GS QKD 014 v1.1.1 (2019-02) page 16, table 11)
		key = base64.b64encode(key)
		# append index to key ID
		keyID = keyID + "-" + str(index)
		kidlist.append(keyID)
		# append key and key ID to related variables
		kcollection.append({"key_ID" : keyID, "key" : key})
	

	# send same key_IDs to target KME to let it reserve to this SAE
	if USE_TLS:	
		x = requests.post('https://' + str(tKME_data[KME_IP]) + ':' + str(tKME_data[KME_PORT]) + '/api/v1/kids/' + masterSAE_ID, data = json.dumps({'length': keysLen, "kidlist" : kidlist, 'KME_ID' : str(prefs['settings']['KME_ID'])}), verify=verifyCert, cert=(clientCert, clientKey))
	else:
		x = requests.post('http://' + str(tKME_data[KME_IP]) + ':' + str(tKME_data[KME_PORT]) + '/api/v1/kids/' + masterSAE_ID, data = json.dumps({'length': keysLen, "kidlist" : kidlist, 'KME_ID' : str(prefs['settings']['KME_ID'])}))
	if x.status_code == 401:
		# try to authenticate
		if doAuth(tKME_data[KME_ID]) is True:
			# try the request again
			if USE_TLS:
				x = requests.post('https://' + str(tKME_data[KME_IP]) + ':' + str(tKME_data[KME_PORT]) + '/api/v1/kids/' + masterSAE_ID, data = json.dumps({'length': keysLen, "kidlist" : kidlist, 'KME_ID' : str(prefs['settings']['KME_ID'])}), verify=verifyCert, cert=(clientCert, clientKey))
			else:
				x = requests.post('http://' + str(tKME_data[KME_IP]) + ':' + str(tKME_data[KME_PORT]) + '/api/v1/kids/' + masterSAE_ID, data = json.dumps({'length': keysLen, "kidlist" : kidlist, 'KME_ID' : str(prefs['settings']['KME_ID'])}))
	if x.status_code != 200:
		# error
		log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because of an internal server error.")
		cursor.execute("UNLOCK TABLES")
		reply = {"message" : "Server Error"}
		return json.dumps(reply), 503

	
	return json.dumps(str(kcollection)), 200



@app.route('/api/v1/keys/<master_SAE_ID>/dec_keys', methods=['POST'])
@oidc.accept_token(True)
def getKeyWithKeyIDs(master_SAE_ID):
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	log(INFO, "Key with key ID requested by client " + g.oidc_token_info['client_id'])
	master_SAE_ID = str(master_SAE_ID)
	req_data = json.loads(request.data)
	if "key_IDs" not in req_data:
		log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because of a malformed request.")
		reply = {"message" : "Request must contain a dictionary where 'key_IDs' is the key to access the array with requested key IDs."}
		return json.dumps(reply), 400
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()

	# get KME associated to this SAE
	try:
		cursor.execute("SELECT KME_ID FROM destinations WHERE SAE_ID = '%s'" % master_SAE_ID)
		tKME_ID = cursor.fetchone()
		if tKME_ID is None:
			# destination not known - query all known KME to check if someone konws it
			cursor.execute("SELECT * FROM exchangedKeys")
			kme_list = cursor.fetchall()
			for kme in kme_list:
				if USE_TLS:
					x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + master_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
				else:
					x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + master_SAE_ID)
				if x.status_code == 401:
					# try to authenticate
					if doAuth(kme[KME_ID]) is True:
						# try the request again
						if USE_TLS:
							x = requests.get('https://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + master_SAE_ID, verify=verifyCert, cert=(clientCert, clientKey))
						else:
							x = requests.get('http://' + str(kme[KME_IP]) + ':' + str(kme[KME_PORT]) + '/api/v1/saes/' + master_SAE_ID)
				if x.status_code == 200:
					# update destinations
					cursor.execute("INSERT INTO destinations (SAE_ID, KME_ID) VALUES ('%s', '%s')" % (master_SAE_ID, kme[KME_ID]))
					tKME_ID = kme[KME_ID]
					break
			if tKME_ID is None:
				# requested SAE does not exist in this network - report the error
				log(ERROR, "Key request from client " + g.oidc_token_info['client_id'] + " failed because destination is not known.")
				reply = {"message" : "Bad request format", "details" : [{"SAE_ID error" : "Requested SAE_ID is not known in the network"}]}
				return json.dumps(reply), 400
		else:
			tKME_ID = tKME_ID[0]
		# check that all requested keys have been reserved for this SAE
		cursor.execute("LOCK TABLES reservedKeys WRITE")
		cursor.execute("SELECT SAEKeys FROM reservedKeys WHERE KME_ID = '%s'" % tKME_ID)
		SAEKeys = cursor.fetchone()
		if SAEKeys is None:
			# error - no key reserved for this SAE
			cursor.execute("UNLOCK TABLES")
			log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because requested keys are not reserved for this client.")
			reply = {"message" : "Requested keys are not reserved for this SAE."}
			return json.dumps(reply), 400
		SAEKeys = SAEKeys[0]
		reservedKeys = json.loads(SAEKeys)
		if master_SAE_ID not in reservedKeys:
			# error - no key reserved for this SAE
			cursor.execute("UNLOCK TABLES")
			log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because requested keys are not reserved for this client.")
			reply = {"message" : "Requested keys are not reserved for this SAE."}
			return json.dumps(reply), 400

		# return keys
		kidlist = req_data["key_IDs"]
		keysNo = len(kidlist)
		kcollection = []
		client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
		client.token = prefs['vault']['token']
		response = client.secrets.kv.read_secret_version(path='storedkeys')
		keys = response['data']['data']['keys']
		if keysNo > len(keys):
			# error - this is not supposed to happen
			cursor.execute("UNLOCK TABLES")
			log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because of an intenal server error.")
			reply = {"message" : "Server Error"}
			return json.dumps(reply), 503
		availableKeys = reservedKeys[master_SAE_ID]
		keysNo = len(kidlist)
		for kidEntry in kidlist:
			kid = kidEntry['key_ID']
			# check that requested key has been reserved for this SAE
			if kid not in availableKeys:
				cursor.execute("UNLOCK TABLES")
				# error - requested key is not reserved for this SAE
				log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because requested keys are not reserved for this client.")
				reply = {"message" : "Requested key ID %s is not reserved for this SAE." % kid}
				return json.dumps(reply), 400
			key = eval(keys.pop(kid))
			# encode key to base64 as per QKD specifications (ETSI GS QKD 014 v1.1.1 (2019-02) page 16, table 11)
			key = base64.b64encode(key)
			kcollection.append({"key_ID" : kid, "key" : key})
			availableKeys.remove(kid)

		# remove selected keys from storage
		client.secrets.kv.v2.create_or_update_secret(path='storedkeys', secret=dict(keys=keys),)
		# update reservedKeys
		cursor.execute("UPDATE reservedKeys SET SAEKeys = '%s' WHERE KME_ID = '%s'" % (json.dumps({master_SAE_ID : availableKeys}), tKME_ID))
		cursor.execute("UNLOCK TABLES")
		return json.dumps({"keys" : str(kcollection)}), 200
	except Exception as e:
		cursor.execute("UNLOCK TABLES")
		log(ERROR, "Key with key ID request from client " + g.oidc_token_info['client_id'] + " failed because of an intenal server error.")
		return "Server error", 503




@app.route('/api/v1/preferences', methods=['GET'])
@oidc.accept_token(True)
def getPreferences():
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	log(INFO, "Internal preferences queried by client " + g.oidc_token_info['client_id'])
	result = {}
	for pref in prefs['global'].keys():
		if pref == 'log_level':
			if prefs['global'][pref] == 0:
				result[pref] = 'INFO'
			elif prefs['global'][pref] == 1:
				result[pref] = 'WARNING'
			else:
				result[pref] = 'ERROR'
		else:
			result[pref] = prefs['global'][pref]
	return json.dumps(result)

@app.route('/api/v1/keys/preferences/<preference>', methods=['POST'])
@oidc.accept_token(True)
def setPreference(preference):
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	value = json.loads(request.data)
	try:
		# try to access required preference. If it doesn't exist, KeyError will be raised
		if preference == 'log_level':
			if value == 'INFO':
				prefs['global'][preference] = 0
			elif value == 'WARNING':
				prefs['global'][preference] = 1
			elif value == 'ERROR':
				prefs['global'][preference] = 2
			else:
				# log level different by the three above is not allowed
				reply = {"message" : "Requested log level is not allowed. Allowed levels are 'INFO', 'WARNING', 'ERROR'"}
				return json.dumps(reply), 400
		elif preference == 'timeout':
			prefs['global'][preference] = int(value)
		else:
			prefs['global'][preference] = value
		log(INFO, 'Client ' + g.oidc_token_info['client_id'] + ' has changed preference "' + preference + '" to value "' + value + '"')
		return json.dumps("OK"), 200
	except KeyError:
		reply = {"message" : "The preference you are trying to change does not exist"}
		return json.dumps(reply), 400
	except Exception as e:
		reply = {"message" : "Server error"}
		return json.dumps(reply), 503


@app.route('/api/v1/keys/information/<info>', methods=['GET'])
@oidc.accept_token(True)
def getInfo(info):
	#if not isAuthenticated(g.oidc_token_info):
	#	return "Unauthorized", 401
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	if info == "qkd_devices":
		result = {}
		cursor.execute("SELECT * FROM qkdmodules")
		modules = cursor.fetchall()
		for mod in modules:
			# append uuid and protocol
			result[mod[ID]] = mod[PROTOCOL]
		return json.dumps({"modules": result})
	if info == "log":
		# parse query parameters
		level = request.args.get('level')
		startT = request.args.get('startTime')
		if startT is not None:
			try:
				# check that start time is expressed as required
				time.strptime(startT, "%Y-%m-%d %H:%M:%S")
			except ValueError:
				reply = {"message" : "Malformed request. Start time must be expressed as 'Year-Month-Day Hour:minute:second'. Example '2020-07-20 16:53:15'"}
				return json.dumps(reply), 400
		if level is not None:
			if level == "INFO":
				level = 0
			elif level == "WARNING":
				level = 1
			elif level == "ERROR":
				level = 2
			else:
				reply = {"message" : "Requested log level is not allowed. Allowed levels are 'INFO', 'WARNING', 'ERROR'"}
				return json.dumps(reply), 400
		# retrieve data from log db
		if level is None and startT is None:
			# no query parameter - return the whole log
			cursor.execute("SELECT * FROM log")
		elif startT is None:
			# only level specified - return the whole history with specified level
			cursor.execute("SELECT * FROM log WHERE level = %d" % level)
		elif level is None:
			# only start time is specified - return all levels messages starting from required date
			cursor.execute("SELECT * FROM log WHERE timestamp >= '%s'" % startT)
		else:
			# both start time and level specified
			cursor.execute("SELECT * FROM log WHERE timestamp >= '%s AND level = %d'" % (startT, level))
		# return results
		result = cursor.fetchall()
		return json.dumps(str(result))

# communication functions to exchange data with other KME

@app.route('/api/v1/challenges/kme', methods=['GET'])
def challengeK():
	# generate a challenge message
	message = str(datetime.now())
	# save and associate it to the requester's IP address
	requester = str(request.remote_addr)
	challenges[requester] = message
	# return challenge
	return json.dumps(message), 200


@app.route('/api/v1/authenticate/kme', methods=['POST'])
def authenticateKme():
	req_data = json.loads(request.data)
	key_id = req_data['key_id']
	message = req_data['message']
	hmac = eval(req_data['hmac'])
	requester = str(request.remote_addr)
	log(INFO, "Authentication request from " + requester)

	try:
		if message != challenges[requester]:
			# error - kme must authenticate by using a string provided by us
			authenticatedHost[requester] = [0, False]
			log(WARNING, "Authentication of KME " + requester + " failed!")

		client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
		client.token = prefs['vault']['token']
		response = client.secrets.kv.read_secret_version(path='storedkeys')
		keys = response['data']['data']['keys']
		key = keys[key_id]
		# convert key to bytes
		key = bytes(key, 'utf-8')

		# delete authentication message from storage - if KME needs to authenticate again it will need to request a new challenge message
		del challenges[requester]

		# deserialize hmac
		hmac = base64.b64decode(hmac)
		if verify(hmac, key, message) == True:
			# authorize client to access our rest api
			authenticatedHost[requester] = [0, True]
			return "OK", 200
		else:
			# authentication failed
			authenticatedHost[requester] = [0, False]
			log(WARNING, "Authentication of KME " + requester + " failed!")
			return "Unauthorized", 401
	except Exception as e:
		# authentication failed
		authenticatedHost[requester] = [0, False]
		log(WARNING, "Authentication of KME " + requester + " failed!")
		return "Unauthorized", 401

@app.route('/api/v1/saes/<slave_SAE_ID>', methods=['GET'])
def knownSAE(slave_SAE_ID):
	req = {'client_id': str(request.remote_addr), 'session_state' : 0} 
	if not isAuthenticated(req):
		return "Unauthorized", 401

	# check if requested SAE is attached to us
	slave_SAE_ID = str(slave_SAE_ID)
	log(INFO, "Client " + str(request.remote_addr) + " asked if " + slave_SAE_ID + " is a known SAE for us")
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	cursor.execute("SELECT * FROM connectedSAE WHERE SAE_ID = '%s'" % slave_SAE_ID)
	result = cursor.fetchone()
	if result is None:
		# requested SAE is not known to us
		return "Not Found", 404
	else:
		# SAE is attached to us
		return "OK", 200


@app.route('/api/v1/kids/<master_SAE_ID>', methods=['POST'])
def reserveKeys(master_SAE_ID):
	req = {'client_id': str(request.remote_addr), 'session_state' : 0} 
	if not isAuthenticated(req):
		return "Unauthorized", 401
	master_SAE_ID = str(master_SAE_ID)

	log(INFO, "Keys reservation requested by " + master_SAE_ID)
	req_data = json.loads(request.data)
	klen = req_data['length']
	kids = req_data['kidlist']
	KMEid = req_data['KME_ID']
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	# use a lock to access database to avoid concurrency access
	try:
		cursor.execute("SELECT * FROM KmeExchangerData WHERE KME_ID = '%s'" % KMEid)
		result = cursor.fetchall()
		if result is None or result == []:
			log(ERROR, "Key reservation requested by " + master_SAE_ID + " failed because no KME with ID " + KMEid + " was found in KmeExchangerData table")
			return "Data mismatch", 400
		for exchange in result:
			if exchange[KEY_HANDLE] != None:
				break

		cursor.execute("SELECT * FROM qkdmodules WHERE moduleID = '%s'" % exchange[MODULE_ID])
		module = cursor.fetchone()
		if module is None:
			# error - this is not supposed to happen
			# module does not exist - remove all entries that refer to it
			cursor.execute("DELETE FROM KmeExchangerData WHERE module_ID = '%s'" % exchange[MODULE_ID])
			log(ERROR, "Key reservation requested by " + master_SAE_ID + " failed because no module connected with destination has been established.")
			return "No module found", 400

		# keys are exchanged in chunks of 128 bits (16 bytes), check the number of chunks requested to meet key length specification
		requiredKeys = math.ceil(klen / 16)
		current_module = module[MODULE]
		x = requests.post('http://' + current_module + '/available_keys', data=repr([exchange[KEY_HANDLE]]))
		if x.status_code != 200:
			availKeys = 0
		else:
			availKeys = int(eval(x.content)[0])
		# check that enough keys are available
		if (len(kids)*requiredKeys) > availKeys:
			cursor.execute("UNLOCK TABLES")
			# error - this is not supposed to happen
			log(ERROR, "Keys reservation requested by " + master_SAE_ID + " failed because of not enough keys are available")
			cursor.execute("UNLOCK TABLES")
			return "Not enough keys", 400

		cursor.execute("LOCK TABLES reservedKeys WRITE")
		for i in range(len(kids)):
			# get the correct index of the key to retrieve
			index = kids[i].split('-')
			index = int(index[-1])

			key = bytearray()
			for j in range(requiredKeys):
				x = requests.post('http://' + current_module + '/get_key', data=repr([exchange[KEY_HANDLE], -1, None]))
				if x.status_code != 200:
					log(ERROR, "Key reservation requested by " + master_SAE_ID + " failed because key with streamID %s and index %s is not available." % (exchange[KEY_HANDLE], index))
					return "key unavailable", 400
				else:
					chunk, midIndex, status = eval(x.content)
	
				key = key + chunk
				index = index + 1

			# make sure key has the right size
			key = key[:klen]

			# save reserved key in vault
			client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
			client.token = prefs['vault']['token']
			response = client.secrets.kv.read_secret_version(path='storedkeys')
			keys = response['data']['data']['keys']
			keys[kids[i]] = str(key)
			client.secrets.kv.v2.create_or_update_secret(path='storedkeys', secret=dict(keys=keys),)


		cursor.execute("SELECT SAEKeys FROM reservedKeys WHERE KME_ID = '%s'" % KMEid)
		SAEKeys = cursor.fetchone()
		if SAEKeys is None:
			# insert key IDs with related SAE to reserve
			cursor.execute("LOCK TABLES reservedKeys WRITE")
			cursor.execute("INSERT INTO reservedKeys (KME_ID, SAEKeys) VALUES ('%s', '%s')" % (KMEid, json.dumps({master_SAE_ID : kids})))
	
			cursor.execute("UNLOCK TABLES")
			return "OK", 200

		# KME ID already present
		SAEKeys = SAEKeys[0]
		reservedKeys = json.loads(SAEKeys)

		if master_SAE_ID in reservedKeys:
			for k in kids:
				reservedKeys[master_SAE_ID].append(k)
		else:
			reservedKeys[master_SAE_ID] = kids


		# update key IDs with related SAE to reserve
		cursor.execute("UPDATE reservedKeys SET SAEKeys = '%s' WHERE KME_ID = '%s'" % (json.dumps(reservedKeys), KMEid))
		cursor.execute("UNLOCK TABLES")
		return "OK", 200

	except Exception as e:
		app.logger.info("Exception: %s" % str(e)) # [cr] remove
		cursor.execute("UNLOCK TABLES")
		log(ERROR, "Keys reservation requested by " + master_SAE_ID + " failed because of an internal server error")
		return "Server error", 503


@app.route('/api/v1/keys/', methods=['POST'])
def openRequest():
	req = {'client_id': str(request.remote_addr), 'session_state' : 0} 
	if not isAuthenticated(req):
		return "Unauthorized", 401

	log(INFO, "Client " + str(request.remote_addr) + " transmitted us key handle and ID for QKD_Open function")
	data = json.loads(request.data)
	key_handle = None
	targetAddress = None
	KID = data["key id"]
	tKME_ID = data["KME_ID"]
	if data.get("key handle") is not None:
		key_handle = data["key handle"]
	if data.get("module address") is not None:
		targetAddress = data["module address"]
	# retrieve KME_ID from which the request come from
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	# check if this is the first request
	if targetAddress is not None:
		# check if there's a qkd module available for this request
		current_module, module_ID, address = getQKDModule()
		if current_module == None:
			# no QKD module available, reply with error
			return "Server Error", 503
		# insert request in exchanger data DB
		cursor.execute("INSERT INTO KmeExchangerData (KME_ID, key_handle, key_ID, open, module_ID, module_address) VALUES ('%s', NULL, '%s', 0, '%s', '%s')" % (tKME_ID, KID, module_ID, targetAddress))
		return address, 200
	# check if it is the second request instead
	elif key_handle is not None:
		# update KmeExchangerData with key_handle
		cursor.execute("UPDATE KmeExchangerData SET key_handle = '%s' WHERE key_ID = '%s'" % (key_handle, KID))
		cursor.execute("SELECT * from KmeExchangerData WHERE key_ID = '%s'" % (KID))
		result = cursor.fetchone()
		moduleID = result[4]
		cursor.execute("SELECT * FROM qkdmodules WHERE moduleID = '%s'" % moduleID)
		module = cursor.fetchone()
		current_module = module[MODULE]
		qos = {'timeout' : prefs['global']['timeout'], 'length' : 128} # [cr] TODO: better management
		x = requests.post('http://' + current_module + '/open_connect', data=repr([None, result[TARGET_ADDRESS], qos, key_handle]))
		return "OK", 200


@app.route('/api/v1/keys/key', methods=['POST'])
def syncRequest():
	req = {'client_id': str(request.remote_addr), 'session_state' : 0} 
	if not isAuthenticated(req):
		return "Unauthorized", 401

	try:
		# get key id
		data = json.loads(request.data)
		KID = data["key id"]
		log(INFO, "Client " + str(request.remote_addr) + " is requesting synchronization of key " + str(KID))
		# check if key is in valut
		client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
		client.token = prefs['vault']['token']
		response = client.secrets.kv.read_secret_version(path='storedkeys')
		keys = response['data']['data']['keys']
		# if key doesn't exist KeyError exception will be thrown on the next line of code
		key = keys[KID]
		# if we are here exception didn't occur and we can say synchronization is complete
		completedKeys[KID] = True
		return json.dumps("OK"), 200
	except KeyError:
		return json.dumps("Not found"), 404
	except Exception as e:
		return json.dumps("Internal Server Error"), 503



# SOUTHBOUND Interface functions
@app.route('/api/v1/keys/modules', methods=['POST'])
def registerModule():
	req = eval(request.data)
	protocol = req[0]
	moduleAddress = req[1]
	max_key_count = int(req[2])
	
	moduleID = str(uuid.uuid4())
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	cursor.execute("INSERT INTO qkdmodules (moduleID, module, protocol, moduleIP, max_key_count) VALUES ('%s', '%s', '%s', '%s', %d)" % (moduleID, moduleAddress, protocol, moduleAddress, max_key_count))
	return "OK"


# Utility functions
def getQKDModule():
	# look for an available QKDModule with required protocol
	# required protocol can be found in preferences
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	cursor.execute("SELECT * FROM qkdmodules")
	modules = cursor.fetchall()
	current_module = None
	lock = None
	module_ID = None
	address = None
	m = None
	for mod in modules:
		m = mod[MODULE]
		module_ID = mod[ID]
		address = mod[MODULE_IP]
		if local_modules.get(module_ID) is None:
			local_modules[module_ID] = Lock()
		lock = local_modules[module_ID]
		if not lock.locked():
			# select first available module
			# lock can also be acquired by someone else in the meantime. This is not a problem since lock will always be tested before using module. This check just try to select less used modules to balance load.
			current_module = m
			if mod[PROTOCOL] == prefs['global']['qkd_protocol']:
				# stop searching if available module implements the desired qkd protocol
				break
	if current_module is None and m is not None:
		# all modules are busy, select last module. All requests will be queued
		current_module = m
	return current_module, module_ID, address


def doAuth(kmeID):
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
	cursor = db.cursor()
	cursor.execute("SELECT * FROM exchangedKeys WHERE KME_ID = '%s'" % kmeID)
	KME = cursor.fetchone()
	if KME is None:
		# error
		return
	try:
		# get the string
		kid = KME[AUTH_KEY_ID]
		# get the correspondant key in vault
		client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
		client.token = prefs['vault']['token']
		response = client.secrets.kv.read_secret_version(path='storedkeys')
		keys = response['data']['data']['keys']
		#app.logger.info
		key = bytes(keys[kid], 'utf-8')
		# get the challenge message
		if USE_TLS:
			x = requests.get('https://' + str(KME[KME_IP]) +  ':' + str(KME[KME_PORT]) + '/api/v1/challenges/kme', verify=verifyCert, cert=(clientCert, clientKey))
		else:
			x = requests.get('http://' + str(KME[KME_IP]) +  ':' + str(KME[KME_PORT]) + '/api/v1/challenges/kme')
		if x.status_code != 200:
			return False
		challenge = json.loads(x.content)
		# calculate hmac
		hmac = authenticate(key, challenge)
		# serialize hmac for transmission
		hmac = base64.b64encode(hmac)
		if USE_TLS:
			x = requests.post('https://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/authenticate/kme', data = json.dumps({"key_id" : kid, "message" : challenge, "hmac" : str(hmac)}), verify=verifyCert, cert=(clientCert, clientKey))
		else:
			x = requests.post('http://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/authenticate/kme', data = json.dumps({"key_id" : kid, "message" : challenge, "hmac" : str(hmac)}))
		if x.status_code == 200:
			return True
		return False
	except Exception as e:
		return False


# QKD Implementation: This class actually perform QKD operations
class KeyExchanger(Thread):
	def __init__(self):
		Thread.__init__(self)


	def run(self):
		db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
		cursor = db.cursor()

		while True:
			try:
				# get KMEs list
				cursor.execute("SELECT * FROM exchangedKeys")
				KMElist = cursor.fetchall()
				for KME in KMElist:
					if KME[KEY_COUNT] == KME[MAX_KEY_COUNT]:
						# selected KME cannot save more keys, skip it
						continue

					# check if there's an exchange to be performed with this KME
					cursor.execute("SELECT * FROM KmeExchangerData WHERE KME_ID = '%s'" % KME[KME_ID])
					exchanges = cursor.fetchall()
					if exchanges == []:
						# no exchange is in progress with this KME - start a new one
						current_module, module_ID, module_address = getQKDModule()
						if current_module == None:
							# no QKD module available, move forward
							continue

						# start key exchange
						lock = local_modules[module_ID]
						if not lock.acquire(False):
							# this module is used by someone else. go ahead for now
							continue

						KID = str(uuid.uuid4())
						# send KEY_ID and QKD module address to target KME
						if USE_TLS:
							x = requests.post('https://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key id" : KID, "module address" : module_address, "KME_ID" : prefs['settings']['KME_ID']}), verify=verifyCert, cert=(clientCert, clientKey))
						else:
							x = requests.post('http://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key id" : KID, "module address" : module_address, "KME_ID" : prefs['settings']['KME_ID']}))
						if x.status_code == 401:
							# try to authenticate
							if doAuth(KME[KME_ID]) is True:
								# try the request again
								if USE_TLS:
									x = requests.post('https://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key id" : KID, "module address" : module_address, "KME_ID" : prefs['settings']['KME_ID']}), verify=verifyCert, cert=(clientCert, clientKey))
								else:
									x = requests.post('http://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key id" : KID, "module address" : module_address, "KME_ID" : prefs['settings']['KME_ID']}))
						if x.status_code == 200:
							# get IP address of target QKD module
							moduleAddress = bytes.decode(x.content, 'utf-8').rstrip()
							qos = {'timeout' : prefs['global']['timeout'], 'length' : KME[MAX_KEY_SIZE]}
							x = requests.post('http://' + current_module + '/open_connect', data=repr([None, moduleAddress, qos, None]))
							# let this module available for others
							lock.release()
							if x.status_code != 200:
								# error - move forward
								continue
							response = eval(x.content)
							key_handle = response[0]
							status = response[1]
							
							# send key_handle to target KME
							if USE_TLS:
								x = requests.post('https://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key handle" : key_handle, "key id" : KID, "KME_ID" : prefs['settings']['KME_ID']}), verify=verifyCert, cert=(clientCert, clientKey))
							else:
								x = requests.post('http://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key handle" : key_handle, "key id" : KID, "KME_ID" : prefs['settings']['KME_ID']}))
							if x.status_code == 401:
								# try to authenticate
								if doAuth(KME[KME_ID]) is True:
									# try the request again
									if USE_TLS:
										x = requests.post('https://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key handle" : key_handle, "key id" : KID, "KME_ID" : prefs['settings']['KME_ID']}), verify=verifyCert, cert=(clientCert, clientKey))
									else:
										x = requests.post('http://' + str(KME[KME_IP]) + ':' + str(KME[KME_PORT]) + '/api/v1/keys/', data = json.dumps({"key handle" : key_handle, "key id" : KID, "KME_ID" : prefs['settings']['KME_ID']}))
							if x.status_code == 200:
								# target KME registered key handle and ID, register them on this side too
								cursor.execute("INSERT INTO KmeExchangerData (KME_ID, key_handle, key_ID, open, module_ID, module_address) VALUES ('%s', '%s', '%s', 1, '%s', '%s')" % (KME[KME_ID], key_handle, KID, module_ID, moduleAddress))
						# we just opened the connection, give time to target KME to do the same, hence go ahead with the next KME
						continue

			except Exception as e:
				app.logger.info("Exception: %s" % str(e)) # [cr] remove
				try:
					if lock.locked():
						lock.release()
					cursor.execute("UNLOCK TABLES")
				except:
					pass
				# make sure this thread never returns
				continue



def main():
	global serverPort
	# check for port parameter
	try:
		port = eval(sys.argv[1])
		if isinstance(port, int):
			serverPort = port
	except:
		pass

	# check for key storage
	client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
	client.token = prefs['vault']['token']
	try:
		if client.sys.is_sealed():
			# unseal vault so that key storage can be used through the program lifecycle
			client.sys.submit_unseal_key(prefs['vault']['unseal1'])
			client.sys.submit_unseal_key(prefs['vault']['unseal2'])
		if client.sys.is_sealed():
			print("CRITICAL ERROR - cannot unseal vault storage. Quitting...")
			sys.exit(2)
	except Exception as e:
		print("CRITICAL ERROR - cannot access vault storage. Quitting...")
		sys.exit(2)

	# launch key exchanger thread
	ke = KeyExchanger()
	ke.start()
	# launch server
	fh = logging.FileHandler('server.log')
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	fh.setFormatter(formatter)
	app.logger.addHandler(fh)
	app.logger.setLevel(logging.DEBUG)
	if USE_TLS:
		context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
		context.verify_mode = ssl.CERT_OPTIONAL
		context.load_verify_locations(verifyCert)
		context.load_cert_chain(serverCert, serverKey)
		app.run(host='0.0.0.0', port=serverPort, ssl_context=context)
	else:
		app.run(host='0.0.0.0', port=serverPort)
	ke.join()

if __name__ == "__main__":
	main()
