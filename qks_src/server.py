from flask import request, Flask
import requests 
import vaultClient 
import uuid 
import json
import sys

app = Flask(__name__)
serverPort = 8080 
prefix = "/api/v1"

dafult_key_size = 128

# NORTHBOUND INTERFACE 
@app.route(prefix+"/keys/<slave_SAE_ID>/status", methods=['GET'])
def getStatus(slave_SAE_ID):
    # TODO: api function
    slave_SAE_ID = str(slave_SAE_ID)
    return f"get getStatus for {slave_SAE_ID}", 200

@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
def getKey(slave_SAE_ID):
    # TODO: api function
    slave_SAE_ID = str(slave_SAE_ID)
    content = request.get_json()
    if (type(content) is dict) : 
        number = content['number'] if 'number' in content else 1
        key_size = content['size'] if 'size' in content else dafult_key_size
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        extension_optional = content['extension_optional'] if 'extension_optional' in content else None
        #call function
        status = 200
        value = {'number' : number, 'size' : key_size}

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
            value = {'ids' : key_IDs}
    
            return value, status

    value = {'message' : "bad request: request does not contains a valid json object"}
    return value, 500 

@app.route(prefix+"/qkdms", methods=['GET'])
def getQKDMs(): 
    # TODO: api function
    return "get getQKDMS", 200

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
def setPreferences(preference) : 
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




def main() : 
    global app, serverPort

    if (len(sys.argv) > 1) : 
        try: 
            serverPort = int(sys.argv[1])
            if (serverPort < 0 or serverPort > 2**16 - 1):
                raise Exception
        except: 
            print("ERROR: use 'python3 appname <port>', port must be integer")

    # check vault init
    # check db init 

    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
