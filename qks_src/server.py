from flask import request, Flask

import requests 
import sys
import api

app = Flask(__name__)
serverPort = 4000
prefix = "/api/v1"



# NORTHBOUND INTERFACE 
@app.route(prefix+"/keys/<slave_SAE_ID>/status", methods=['GET'])
def getStatus(slave_SAE_ID):
    slave_SAE_ID = str(slave_SAE_ID)
    master_SAE_ID = None # TODO: get it from authentication! 
    status, value = api.getStatus(slave_SAE_ID, master_SAE_ID)
    if status: 
        return value, 200
    else: 
        return value, 404


@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
def getKey(slave_SAE_ID):
    slave_SAE_ID = str(slave_SAE_ID)
    master_SAE_ID = None # TODO: get it from authentication! 
    content = request.get_json()
    try: 
        master_SAE_ID = content['master_SAE_ID'] # TO BE REMOVED
        number = int(content['number']) if 'number' in content else 1
        key_size = int(content['size']) if 'size' in content else None
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        status, value = api.getKey(slave_SAE_ID, master_SAE_ID, number, key_size, extension_mandatory)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/keys/<master_SAE_ID>/dec_keys", methods=['POST'])
def getKeyWithKeyIDs(master_SAE_ID):
    slave_SAE_ID = None # TODO: get it from authentication! 
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json() 
    try:      
        key_IDs = list(content['key_IDs'])
        status, value = api.getKeyWithKeyIDs(master_SAE_ID, key_IDs, slave_SAE_ID)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/qkdms", methods=['GET'])
def getQKDMs(): 
    status, value = api.getQKDMs()
    if status: 
        return value, 200
    else:
        value = {'message' : "internal error"}
        return value, 503

@app.route(prefix+"/saes", methods=['POST'])
def registerSAE(): 
    content = request.get_json()
    try:
        sae_ID = str(content['id'])
        status, value = api.registerSAE(sae_ID) 
        if status:
            return value, 200
        else:
            return value, 503
    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/saes/<SAE_ID>", methods=['DELETE'])
def unregisterSAE(SAE_ID): 
    SAE_ID = str(SAE_ID)
    status, value = api.unregisterSAE(SAE_ID) 
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/preferences", methods=['GET'])
def getPreferences() : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    status = True
    value = {'preferences': [{'preference1' : 'val1'}]}
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/preferences/<preference>", methods=['PUT'])
def setPreference(preference) : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    content = request.get_json()
    try:
        if preference == str(content['preference']):
            new_value = content['value']
            status, value = (True, {'message': f"preference {preference} updated"})
            if status: 
                return value, 200
            else: 
                return value, 503
    except Exception:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['POST'])
def startQKDMStream(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = api.startQKDMStream(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['DELETE'])
def deleteQKDMStreams(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = api.deleteQKDMStreams(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 503

# SOUTHBOUND INTERFACE 
@app.route(prefix+"/qkdms", methods=['POST'])
def registerQKDM(): 
    content = request.get_json()
    try:
        QKDM_ID = str(content['QKDM_ID'])
        protocol = str(content['protocol']) 
        QKDM_IP = str(content['QKDM_IP']) 
        QKDM_port = int(content['QKDM_port']) 
        reachable_qks = str(content['reachable_QKS'])
        reachable_qkdm = str(content['reachable_QKDM']) 
        max_key_count = int(content['max_key_count']) 
        key_size = int(content['key_size']) 
        
        status, value = api.registerQKDM(QKDM_ID, protocol, QKDM_IP, QKDM_port, reachable_qkdm, reachable_qks, max_key_count, key_size)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/qkdms/<qkdm_ID>", methods=['DELETE'])
def unregisterQKDM(qkdm_ID): 
    qkdm_ID = str(qkdm_ID)
    status, value = api.unregisterQKDM(qkdm_ID) 
    if status: 
        return value, 200
    else: 
        return value, 503 


# EXTERNAL INTERFACE 
@app.route(prefix+"/keys/<master_SAE_ID>/reserve", methods=['POST'])
def reserveKeys(master_SAE_ID):  
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json()
    try:
        key_stream_ID = str(content['key_stream_ID'])
        slave_SAE_ID = str(content['slave_SAE_ID'])
        key_length = int(content['key_length'])
        key_ID_list = list(content['key_ID_list'])

        status, value = api.reserveKeys(master_SAE_ID, slave_SAE_ID, key_stream_ID, key_length, key_ID_list)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

# TODO
@app.route(prefix+"/forward", methods=['POST'])   
def forwardData(): 
    # TODO: api function
    content = request.get_json()
    try:
        data = content['data']
        decryption_key_ID = str(content['decryption_key_ID'])
        decryption_stream_ID = str(content['decryption_key_stream'])
        
        # call function  
        return "ok", 200 
    except: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/streams", methods=['POST'])
def createStream(): 
    content = request.get_json()
    try:
        source_qks_ID = str(content['source_qks_ID'])
        key_stream_ID = str(content['key_stream_ID'])
        stream_type = str(content['type'])
        qkdm_id = str(content['qkdm_id']) if 'qkdm_id' in content else None

        status, value = api.createStream(source_qks_ID, key_stream_ID, stream_type, qkdm_id)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400
        
@app.route(prefix+"/streams/<key_stream_ID>", methods=['DELETE'])
def closeStream(key_stream_ID): 
    key_stream_ID = str(key_stream_ID)
    content = request.get_json() 
    try:
        source_qks_ID = str(content['source_qks_ID'])
        status, value = api.closeStream(key_stream_ID, source_qks_ID)
        if status: 
            return value, 200
        else: 
            return value, 503

    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

def main() : 
    global app, serverPort
            
    # check db init 
    db_init = api.check_mongo_init() 
    if db_init: 
        print("DB initialized successfully")
    else: 
        print("ERROR: unable to access DB")
        return 

    # check vault init
    vault_init = api.check_vault_init() 
    if vault_init: 
        print("Vault initialized successfully")
    else: 
        print("ERROR: unable to access vault")
        return 

    serverPort = api.get_config_port()
    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
