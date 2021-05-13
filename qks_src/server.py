from flask import request, Flask
import requests 
import json
import sys

import api

app = Flask(__name__)
serverPort = 8080 
prefix = "/api/v1"

dafult_key_size = 128

# NORTHBOUND INTERFACE 
@app.route(prefix+"/keys/<slave_SAE_ID>/status", methods=['GET'])
def getStatus(slave_SAE_ID):
    # TODO: api function
    slave_SAE_ID = str(slave_SAE_ID)
    value = {'source_KME_ID' : "qks1",
            'target_KME_ID' : "qks2", 
            'master_SAE_id' : "senderSAE",
            'slave_SAE_id' : slave_SAE_ID}
    return value, 200

@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
def getKey(slave_SAE_ID):
    # TODO: api function
    slave_SAE_ID = str(slave_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) : 
        number =content['number'] if 'number' in content and type(content['number']) is int else 1
        key_size = content['size'] if 'size' in content and type(content['size']) is int else dafult_key_size
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
    # TODO: api function
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) : 
        if 'key_IDs' in content and type(content['key_IDs']) is list:         
            key_IDs = content['key_IDs']
            #call function
            status = 200
            value = {'keys' : [
                {'key_ID' : "id1", 'key' : "key1"}, 
                {'key_ID' : "id2", 'key' : "key2"}, 
            ]}
    
            return value, status

    value = {'message' : "bad request: request does not contains a valid json object"}
    return value, 500 

@app.route(prefix+"/qkdms", methods=['GET'])
def getQKDMs(): 
    # TODO: api function
    value = {'QKDM_list' : [
        {'id' : "id1", 'protocol' : "fake", 'ip' : "ip1", 'destination_QKS' : "qks2"},
        {'id' : "id2", 'protocol' : "fake", 'ip' : "ip2", 'destination_QKS' : "qks3"}

    ]}
    return value, 200

@app.route(prefix+"/saes", methods=['POST'])
def registerSAE(): 
    # TODO: api function
    content = request.get_json()
    if (type(content) is dict) and ('name' in content):
        sae_name = content['name']
        # call function 
        status = 200
        value = {'sae_name' : sae_name}

        return value, status
    else: 
        value = {'message' : "error: invalid content or sae name"}
        return value, 500

@app.route(prefix+"/saes/<SAE_ID>", methods=['DELETE'])
def unregisterSAE(SAE_ID): 
    # TODO: api function
    SAE_ID = str(SAE_ID)
    # call function 
    status = 200
    value = f"delete sae {SAE_ID}"
    return value, status

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
    # TODO: api function
    status = 200
    qkdm_ID = str(qkdm_ID)
    value = f"started stream on module {qkdm_ID} "
    return value, status

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['DELETE'])
def deleteQKDMStreams(qkdm_ID) : 
    # TODO: api function
    status = 200
    qkdm_ID = str(qkdm_ID)
    value = f"deleted all streams on module {qkdm_ID} "
    return value, status

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
    # TODO: api function
    master_SAE_ID = str(master_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('key_stream_ID', 'slave_SAE_ID', 'key_lenght', 'key_ID_list')):
        if (type( content['key_ID_list']) is list): 
            key_stream_ID = content['key_stream_ID']
            slave_SAE_ID = content['slave_SAE_ID']
            key_lenght = int(content['key_lenght'])
            key_ID_list = content['key_ID_list']

            #call function 
            return "ok", 200 

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
    # TODO: api function
    content = request.get_json()
    if (type(content) is dict) and all (k in content for k in ('source_qks_ID', 'key_stream_ID', 'type')):
        # call function 
        source_qks_ID = content['source_qks_ID']
        key_stream_ID = content['key_stream_ID']
        stream_type = content['type']
        qkdm_address = content['qkdm_address'] if 'qkdm_address' in content else None

        value = qkdm_address if qkdm_address is not None else "ok"
        return value, 200 
    else: 
        value = {'message' : "error: invalid content"}
        return value, 500
        
@app.route(prefix+"/streams/<stream_ID>", methods=['DELETE'])
def closeStream(stream_ID): 
    # TODO: api function
    stream_ID = str(stream_ID)
    content = request.get_json() 
    if (type(content) is dict) and ('source_qks_ID' in content):
        source_qks_ID = content['source_qks_ID']
        # call function 
        return "ok", 200

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
        except: 
            print("ERROR: use 'python3 appname <port>', port must be a valid port number")

    # check vault init
    # check db init 

    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
