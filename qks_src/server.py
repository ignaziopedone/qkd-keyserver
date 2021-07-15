from quart import request, Quart
import asyncio
import api
import nest_asyncio
import sys

nest_asyncio.apply()
app = Quart(__name__)
serverPort = 4000
prefix = "/api/v1"



# NORTHBOUND INTERFACE 
@app.route(prefix+"/keys/<slave_SAE_ID>/status", methods=['GET'])
async def getStatus(slave_SAE_ID):
    slave_SAE_ID = str(slave_SAE_ID)
    master_SAE_ID = None # TODO: get it from authentication! 
    status, value = await api.getStatus(slave_SAE_ID, master_SAE_ID)
    if status: 
        return value, 200
    else: 
        return value, 404


@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
async def getKey(slave_SAE_ID):
    slave_SAE_ID = str(slave_SAE_ID)
    master_SAE_ID = None # TODO: get it from authentication! 
    content = await request.get_json()
    try: 
        master_SAE_ID = content['master_SAE_ID'] # TO BE REMOVED
        number = int(content['number']) if 'number' in content else 1
        key_size = int(content['size']) if 'size' in content else None
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        status, value = await api.getKey(slave_SAE_ID, master_SAE_ID, number, key_size, extension_mandatory)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/keys/<master_SAE_ID>/dec_keys", methods=['POST'])
async def getKeyWithKeyIDs(master_SAE_ID):
    slave_SAE_ID = None # TODO: get it from authentication! 
    master_SAE_ID = str(master_SAE_ID)
    content = await request.get_json() 
    try:      
        key_IDs = list(content['key_IDs'])
        status, value = await api.getKeyWithKeyIDs(master_SAE_ID, key_IDs, slave_SAE_ID)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/qkdms", methods=['GET'])
async def getQKDMs(): 
    status, value = await api.getQKDMs()
    if status: 
        return value, 200
    else:
        value = {'message' : "internal error"}
        return value, 503

@app.route(prefix+"/saes", methods=['POST'])
async def registerSAE(): 
    content = await request.get_json()
    try:
        sae_ID = str(content['id'])
        status, value = await api.registerSAE(sae_ID) 
        if status:
            return value, 200
        else:
            return value, 503
    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/saes/<SAE_ID>", methods=['DELETE'])
async def unregisterSAE(SAE_ID): 
    SAE_ID = str(SAE_ID)
    status, value = await api.unregisterSAE(SAE_ID) 
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/preferences", methods=['GET'])
async def getPreferences() : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    status = True
    value = {'preferences': [{'preference1' : 'val1'}]}
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/preferences/<preference>", methods=['PUT'])
async def setPreference(preference) : 
    # TODO: api function
    # PREFERENCES SAVED IN REDIS DUE TO CONSISTENCY
    content = await request.get_json()
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
async def startQKDMStream(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = await api.startQKDMStream(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 503

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['DELETE'])
async def deleteQKDMStreams(qkdm_ID) : 
    qkdm_ID = str(qkdm_ID)
    status, value = await api.deleteQKDMStreams(qkdm_ID)
    if status: 
        return value, 200
    else: 
        return value, 503
    


@app.route(prefix+"/qks", methods=['POST'])
async def registerQKS(): 
    content = await request.get_json()
    try:
        QKS_ID = str(content['QKS_ID'])
        QKS_IP = str(content['QKS_IP']) 
        QKS_port = int(content['QKS_port']) 
        routing_IP = str(content['routing_IP']) 
        routing_port = int(content['routing_port']) 

        
        status, value = await api.registerQKS(QKS_ID, QKS_IP, QKS_port, routing_IP, routing_port)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400


@app.route(prefix+"/qks/<qks_ID>/streams", methods=['DELETE'])
async def deleteIndirectStream(qks_ID) : 
    try: 
        qks_ID = str(qks_ID)
        param = int(request.args.get('force'))
        force_mode = True if param == 1 else False 
        status, value = await api.deleteIndirectStream(qks_ID, force_mode)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400


# SOUTHBOUND INTERFACE 
@app.route(prefix+"/qkdms", methods=['POST'])
async def registerQKDM(): 
    content = await request.get_json()
    try:
        QKDM_ID = str(content['QKDM_ID'])
        protocol = str(content['protocol']) 
        QKDM_IP = str(content['QKDM_IP']) 
        QKDM_port = int(content['QKDM_port']) 
        reachable_qks = str(content['reachable_QKS'])
        reachable_qkdm = str(content['reachable_QKDM']) 
        max_key_count = int(content['max_key_count']) 
        key_size = int(content['key_size']) 
        
        status, value = await api.registerQKDM(QKDM_ID, protocol, QKDM_IP, QKDM_port, reachable_qkdm, reachable_qks, max_key_count, key_size)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/qkdms/<qkdm_ID>", methods=['DELETE'])
async def unregisterQKDM(qkdm_ID): 
    qkdm_ID = str(qkdm_ID)
    status, value = await api.unregisterQKDM(qkdm_ID) 
    if status: 
        return value, 200
    else: 
        return value, 503 


# EXTERNAL INTERFACE 
@app.route(prefix+"/keys/<master_SAE_ID>/reserve", methods=['POST'])
async def reserveKeys(master_SAE_ID):  
    master_SAE_ID = str(master_SAE_ID)
    content = await request.get_json()
    try:
        key_stream_ID = str(content['key_stream_ID'])
        slave_SAE_ID = str(content['slave_SAE_ID'])
        key_size = int(content['key_size'])
        key_ID_list = list(content['key_ID_list'])

        status, value = await api.reserveKeys(master_SAE_ID, slave_SAE_ID, key_stream_ID, key_size, key_ID_list)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/forward", methods=['POST'])   
async def forwardData(): 
    content = await request.get_json()
    try:
        data = str(content['data'])
        decryption_key_ID = content['decryption_key_ID']
        decryption_stream_ID = str(content['decryption_key_stream'])
        iv = str(content['iv'])
        destination_sae = str(content['destination_sae']) 
        
        # call function  
        status, value = await api.forwardData(data, decryption_key_ID, decryption_stream_ID, iv, destination_sae) 
        if status: 
            return value, 200 
        else: 
            return value, 503 
    except: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/streams", methods=['POST'])
async def createStream(): 
    content = await request.get_json()
    try:
        source_qks_ID = str(content['source_qks_ID'])
        key_stream_ID = str(content['key_stream_ID'])
        stream_type = str(content['type'])
        qkdm_id = str(content['qkdm_id']) if 'qkdm_id' in content else None
        master_key_id = str(content['master_key_id']) if 'master_key_id' in content else None
        destination_sae = str(content['destination_sae']) if 'destination_sae' in content else None

        status, value = await api.createStream(source_qks_ID, key_stream_ID, stream_type, qkdm_id, master_key_id, destination_sae)
        if status: 
            return value, 200
        else: 
            return value, 503
    except Exception:
        value = {'message' : "error: invalid content"}
        return value, 400
        
@app.route(prefix+"/streams/<key_stream_ID>", methods=['DELETE'])
async def closeStream(key_stream_ID): 
    key_stream_ID = str(key_stream_ID)
    content = await request.get_json() 
    try:
        source_qks_ID = str(content['source_qks_ID'])
        status, value = await api.closeStream(key_stream_ID, source_qks_ID)
        if status: 
            return value, 200
        else: 
            return value, 503

    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"streams/<key_stream_ID>/exchange", methods=['POST'])
async def exchangeIndirectKey(key_stream_ID) : 
    key_stream_ID = str(key_stream_ID)
    content = await request.get_json() 
    try:
        iv = str(content['iv'])
        number = int(content['number'])
        enc_keys = list(content['enc_keys'])
        ids = list(content['ids'])
        status, value = await api.exchangeIndirectKey(key_stream_ID, iv, number, enc_keys, ids)
        if status: 
            return value, 200
        else: 
            return value, 503

    except Exception: 
        value = {'message' : "error: invalid content"}
        return value, 400


async def main() : 
    global app, serverPort
            
    

    # check db and vault init 
    if len(sys.argv) == 2:
        status, serverPort = await api.init_server(sys.argv[1])
    else: 
        status, serverPort = await api.init_server()
    if not status: 
        print("ERROR : unable to init DB or Vault ")
        return  


    print("SUCCESSFULL INIT: server starting on port", serverPort)
    app.run(host='0.0.0.0', port=serverPort, loop = asyncio.get_event_loop())


if __name__ == "__main__":
	asyncio.run(main())
