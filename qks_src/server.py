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
    master_SAE_ID = None # get it from authentication! 
    status, value = api.getStatus(slave_SAE_ID, master_SAE_ID)
    if status: 
        return value, 200
    else: 
        return value, 404


@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
def getKey(slave_SAE_ID):
    slave_SAE_ID = str(slave_SAE_ID)
    master_SAE_ID = None # get it from authentication! 
    content = request.get_json()
    if (type(content) is dict) and 'master_SAE_ID' in content and type(content['master_SAE_ID']) is str: 
        master_SAE_ID = content['master_SAE_ID'] # TO BE REMOVED
        number =content['number'] if 'number' in content and type(content['number']) is int else 1
        key_size = content['size'] if 'size' in content and type(content['size']) is int else None
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        status, value = api.getKey(slave_SAE_ID, master_SAE_ID, number, key_size, extension_mandatory)
        if status: 
            return value, 200
        else: 
            return value, 503
    else:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/keys/<master_SAE_ID>/dec_keys", methods=['POST'])
def getKeyWithKeyIDs(master_SAE_ID):
    slave_SAE_ID = None # get it from authentication! 
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json() 
    if (type(content) is dict) : 
        if 'key_IDs' in content and type(content['key_IDs']) is list:         
            key_IDs = content['key_IDs']
            status, value = api.getKeyWithKeyIDs(master_SAE_ID, key_IDs, slave_SAE_ID)
            if status: 
                return value, 200
            else: 
                return value, 503

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
    if (type(content) is dict) and ('id' in content) and type(content['id']) is str:
        sae_ID = content['id']
        status, value = api.registerSAE(sae_ID) 
        if status:
            return value, 200
        else:
            return value, 503
    else: 
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

# TODO
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

# TODO
@app.route(prefix+"/preferences/<preference>", methods=['PUT'])
def setPreference(preference) : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    content = request.get_json()
    if (type(content) is dict) and ('preference' in content) and ('value' in content):
        if preference == content['preference']: 
            status, value = (True, {'message': f"preference {preference} updated"})
            if status: 
                return value, 200
            else: 
                return value, 503
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
# TODO
@app.route(prefix+"/qkdms", methods=['POST'])
def registerQKDM(): 
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('QKDM_ID', 'protocol', 'QKDM_IP', 'QKDM_port', 'reachable_QKS', 'reachable_QKDM','max_key_count', 'key_size')):
        QKDM_ID = content['QKDM_ID'] if type(content['QKDM_ID']) is str else None
        protocol = content['protocol'] if type(content['protocol']) is str else None
        QKDM_IP = content['QKDM_IP'] if type(content['QKDM_IP']) is str else None
        QKDM_port = content['QKDM_port'] if type(content['QKDM_port']) is int else None
        reachable_qks = content['reachable_QKS'] if type(content['reachable_QKS']) is str else None
        reachable_qkdm = content['reachable_QKDM'] if type(content['reachable_QKDM']) is str else None
        max_key_count = content['max_key_count'] if type(content['max_key_count']) is int else None
        key_size = content['key_size'] if type(content['key_size']) is int else None
        
        if all (el is not None for el in [QKDM_ID, protocol, QKDM_IP, QKDM_port, reachable_qks, reachable_qkdm, max_key_count, key_size]): 
            status, value = api.registerQKDM(QKDM_ID, protocol, QKDM_IP, QKDM_port, reachable_qkdm, reachable_qks, max_key_count, key_size)
            if status: 
                return value, 200
            else: 
                return value, 503

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
    if (type(content) is dict) and all (k in content for k in ('key_stream_ID', 'slave_SAE_ID', 'key_length', 'key_ID_list')):
        if (type( content['key_ID_list']) is list): 
            key_stream_ID = content['key_stream_ID']
            slave_SAE_ID = content['slave_SAE_ID']
            key_length = int(content['key_length'])
            key_ID_list = content['key_ID_list']

            status, value = api.reserveKeys(master_SAE_ID, slave_SAE_ID, key_stream_ID, key_length, key_ID_list)
            if status: 
                return value, 200
            else: 
                return value, 503

    value = {'message' : "error: invalid content"}
    return value, 400

# TODO
@app.route(prefix+"/forward", methods=['POST'])   
def forwardData(): 
    # TODO: api function
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('data', 'decryption_key_ID', 'decryption_key_stream')):
        data = content['data']
        decryption_key_ID = content['decryption_key_ID']
        decryption_stream_ID = content['decryption_key_stream']
        
        # call function  
        return "ok", 200 
    else: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/streams", methods=['POST'])
def createStream(): 
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('source_qks_ID', 'key_stream_ID', 'type')):
        source_qks_ID = content['source_qks_ID'] 
        key_stream_ID = content['key_stream_ID']
        stream_type = content['type']
        qkdm_id = content['qkdm_id'] if 'qkdm_id' in content and type(content['qkdm_id']) is str else None

        if type(source_qks_ID) is str and type(key_stream_ID) is str and type(stream_type) is str:
            status, value = api.createStream(source_qks_ID, key_stream_ID, stream_type, qkdm_id)
            if status: 
                return value, 200
            else: 
                return value, 503

    value = {'message' : "error: invalid content"}
    return value, 400
        
@app.route(prefix+"/streams/<key_stream_ID>", methods=['DELETE'])
def closeStream(key_stream_ID): 
    key_stream_ID = str(key_stream_ID)
    content = request.get_json() 
    if (type(content) is dict) and ('source_qks_ID' in content) and type(content['source_qks_ID']) is str:
        source_qks_ID = content['source_qks_ID']
        status, value = api.closeStream(key_stream_ID, source_qks_ID)
        if status: 
            return value, 200
        else: 
            return value, 503

    else: 
        value = {'message' : "error: invalid content"}
        return value, 400

def main() : 
    global app, serverPort

    if (len(sys.argv) > 1) : 
        try: 
            serverPort = int(sys.argv[1])
            if (serverPort < 0 or serverPort > 2**16 - 1):
                raise Exception
        except Exception: 
            print("ERROR: use 'python3 appname <port>', port must be a valid port number")

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

    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
