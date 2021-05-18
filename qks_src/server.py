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
    # TODO: api function
    slave_SAE_ID = str(slave_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) : 
        number =content['number'] if 'number' in content and type(content['number']) is int else 1
        key_size = content['size'] if 'size' in content and type(content['size']) is int else None
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        extension_optional = content['extension_optional'] if 'extension_optional' in content else None
        #call function
        status = 200
        value = {
            'keys' : [
            {'key_ID' : "id1", 'key' : "key1"}, 
            {'key_ID' : "id2", 'key' : "key2"}, 
        ]}

        return value, status
    else:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 500 

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
                return value, 400

    value = {'message' : "bad request: request does not contains a valid json object"}
    return value, 500 

@app.route(prefix+"/qkdms", methods=['GET'])
def getQKDMs(): 
    status, value = api.getQKDMs()
    if status: 
        return value, 200
    else:
        value = {'message' : "internal error"}
        return value, 500

@app.route(prefix+"/saes", methods=['POST'])
def registerSAE(): 
    content = request.get_json()
    if (type(content) is dict) and ('id' in content) and type(content['id']) is str:
        sae_ID = content['id']
        status, value = api.registerSAE(sae_ID) 
        if status:
            return value, 200
        else:
            return value, 400
    else: 
        value = {'message' : "error: invalid content"}
        return value, 500

@app.route(prefix+"/saes/<SAE_ID>", methods=['DELETE'])
def unregisterSAE(SAE_ID): 
    SAE_ID = str(SAE_ID)
    status, value = api.unregisterSAE(SAE_ID) 
    if status: 
        return value, 200
    else: 
        return value, 400

@app.route(prefix+"/preferences", methods=['GET'])
def getPreferences() : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    status = 200
    preferences = {'preferences': [{'preference1' : 'val1'}]}
    return preferences, status

@app.route(prefix+"/preferences/<preference>", methods=['PUT'])
def setPreference(preference) : 
    # TODO: api function
    content = request.get_json()
    if (type(content) is dict) and ('preference' in content) and ('value' in content):
        if preference == content['preference']: 
            status = 200
            value = f"preference {preference} updated"
            return preference, status
    value = {'message' : "bad request: request does not contains a valid json object"}
    return value, 500 

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['POST'])
def startQKDMStream(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = api.startQKDMStream(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 400

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['DELETE'])
def deleteQKDMStreams(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = api.deleteQKDMStreams(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 400

# SOUTHBOUND INTERFACE 
@app.route(prefix+"/qkdms/<qkdm_ID>", methods=['POST'])
def registerQKDM(qkdm_ID): 
    # TODO: api function
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('QKDM_ID', 'protocol', 'QKDM_IP', 'destination_QKS','max_key_count', 'key_size')):
        if (qkdm_ID == content['QKDM_ID']):
            QKDM_ID = content['QKDM_ID']
            protocol = content['protocol']
            QKDM_IP = content['QKDM_IP']
            destination_qks = content['destination_QKS']
            max_key_count = content['max_key_count']
            key_size = content['key_size']
            # call function 
            status = 200
            value = {'database_data' : {}, 'vault_data' : {}}

            return value, status

    value = {'message' : "error: invalid content"}
    return value, 500

@app.route(prefix+"/qkdms/<qkdm_ID>", methods=['DELETE'])
def unregisterQKDM(qkdm_ID): 
    qkdm_ID = str(qkdm_ID)
    # call function
    status = 200
    value = f"delete qkdm {qkdm_ID}"
    return value, status 


# EXTERNAL INTERFACE 
@app.route(prefix+"/keys/<master_SAE_ID>/reserve", methods=['POST'])
def reserveKeys(master_SAE_ID):  
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('key_stream_ID', 'slave_SAE_ID', 'key_lenght', 'key_ID_list')):
        if (type( content['key_ID_list']) is list): 
            key_stream_ID = content['key_stream_ID']
            slave_SAE_ID = content['slave_SAE_ID']
            key_lenght = int(content['key_lenght'])
            key_ID_list = content['key_ID_list']

            status, value = api.reserveKeys(master_SAE_ID, slave_SAE_ID, key_stream_ID, key_lenght, key_ID_list)
            if status: 
                return value, 200
            else: 
                return value, 400

    value = {'message' : "error: invalid content"}
    return value, 500

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
        return value, 500

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
                return value, 400

    value = {'message' : "error: invalid content"}
    return value, 500
        
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
            return value, 400

    else: 
        value = {'message' : "error: invalid content"}
        return value, 500

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
        print("DB init successfully")
    else: 
        print("ERROR: unable to access DB")
        return 

    # check vault init

    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
