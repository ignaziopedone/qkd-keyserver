from quart import request, Quart, g, flask_patch
import asyncio
import api
import nest_asyncio
import sys
import logging 
from flask_oidc import OpenIDConnect
import traceback
import aiohttp

nest_asyncio.apply()
app = Quart(__name__)
serverPort = 4000
prefix = "/api/v1"
logging.basicConfig(filename='qks.log', filemode='w', level=logging.INFO)
http_client : aiohttp.ClientSession = None
keycloak_data = {}

oidc = OpenIDConnect()
oidc.init_app(app)

async def verifyToken(header: str) -> tuple[bool, str, list] : 
    if header is None or header == "": 
        return False, None, None 

    async with http_client.post(f"http://{keycloak_data['address']}:{keycloak_data['port']}/auth/realms/qks/protocol/openid-connect/userinfo", headers={'Authorization' : header}) as ret: 
        ret_val = await ret.json()
        if 'preferred_username' in ret_val and 'realm_access' in ret_val and 'roles' in ret_val['realm_access']: 
            username  = ret_val['preferred_username'] 
            roles = ret_val['realm_access']['roles']
            return True, username, roles 
        else: 
            return False, None, None
        

# NORTHBOUND INTERFACE 
@app.route(prefix+"/keys/<slave_SAE_ID>/status", methods=['GET'])
#@oidc.accept_token(True)
async def getStatus(slave_SAE_ID):
    #roles = g.oidc_token_info['realm_access']['roles']
    #master_SAE_ID = g.oidc_token_info['username']
     
    header = request.headers.get('Authorization')
    res, master_SAE_ID, roles = await verifyToken(header) 
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if not any(r in roles for r in ['sae', 'admin']): 
        value =  {'message' : "ERROR: you are not an authorized SAE or ADMIN"}
        app.logger.info(f"getStatus : rejected unauthorized user {master_SAE_ID}")
        return value, 401

    slave_SAE_ID = str(slave_SAE_ID)

    try: 
        status, value = await api.getStatus(slave_SAE_ID, master_SAE_ID)
        if status: 
            app.logger.info(f"getStatus: completed for master_SAE {master_SAE_ID} and slave_SAE {slave_SAE_ID}")
            return value, 200
        else: 
            app.logger.info(f"getStatus: error for slave_SAE_ID {slave_SAE_ID} - message = {value['message']}")
            return value, 404
    except Exception as e:
        value = {'mesage' : 'Internal server error'} 
        app.logger.error(f"getStatus EXCEPTION: {e}")
        return value, 400


@app.route(prefix+"/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
#@oidc.accept_token(True)
async def getKey(slave_SAE_ID):
    
    #roles = g.oidc_token_info['realm_access']['roles']
    #master_SAE_ID = g.oidc_token_info['username']

    header = request.headers.get('Authorization')
    res, master_SAE_ID, roles = await verifyToken(header) 

    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if 'sae' not in roles: 
        value =  {'message' : "ERROR: you are not an authorized SAE"}
        app.logger.info(f"getKey : rejected unauthorized user {master_SAE_ID}")
        return value, 401
    
    slave_SAE_ID = str(slave_SAE_ID) 
    content = await request.get_json()
    
    try: 
        number = int(content['number']) if 'number' in content else 1
        key_size = int(content['size']) if 'size' in content else None
        extension_mandatory = content['extension_mandatory'] if 'extension_mandatory' in content else None
        status, value = await api.getKey(slave_SAE_ID, master_SAE_ID, number, key_size, extension_mandatory)
        if status: 
            app.logger.info(f"getKey: completed for master_SAE {master_SAE_ID} and slave_SAE {slave_SAE_ID}")
            return value, 200
        else: 
            app.logger.info(f"getKey: error for slave_SAE {slave_SAE_ID} - message = {value['message']}")
            return value, 503
    except Exception as e:
        app.logger.error(f"getKey EXCEPTION: {traceback.format_exc()}")
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/keys/<master_SAE_ID>/dec_keys", methods=['POST'])
#@oidc.accept_token(True)
async def getKeyWithKeyIDs(master_SAE_ID):
    #roles = g.oidc_token_info['realm_access']['roles']
    #slave_SAE_ID = g.oidc_token_info['username']

    header = request.headers.get('Authorization')
    res, slave_SAE_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if 'sae' not in roles: 
        app.logger.info(f"getKeyWithKeyIDs : rejected unauthorized user {slave_SAE_ID}")
        value =  {'message' : "ERROR: you are not an authorized SAE"}
        return value, 401
    
    master_SAE_ID = str(master_SAE_ID)
    content = await request.get_json() 
    try:      
        key_IDs = list(content['key_IDs'])
        status, value = await api.getKeyWithKeyIDs(master_SAE_ID, key_IDs, slave_SAE_ID)
        if status: 
            app.logger.info(f"getKeyWithKeyIDs: completed for master_SAE {master_SAE_ID} and slave_SAE {slave_SAE_ID}")
            return value, 200
        else: 
            app.logger.info(f"getKeyWithKeyIDs: error for master_SAE {master_SAE_ID} - message = {value['message']}")
            return value, 503
    except Exception as e:
        app.logger.error(f"getKeyWithKeyIDs EXCEPTION: {e}")
        value = {'message' : "bad request: request does not contains a valid json object"}
        return value, 400 

@app.route(prefix+"/qkdms", methods=['GET'])
#@oidc.accept_token(True)
async def getQKDMs(): 

    #roles = g.oidc_token_info['realm_access']['roles']
    header = request.headers.get('Authorization')
    res, username, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401
    
    if 'admin' not in roles: 
        app.logger.info(f"getQKDMs : rejected unauthorized user {username}")
        value =  {'message' : "ERROR: you are not an authorized ADMIN"}
        return value, 401

    status, value = await api.getQKDMs()
    if status: 
        app.logger.info(f"getQKDMs: completed")
        return value, 200
    else:
        app.logger.warning(f"getQKDMs: internal error - unable to complete")
        value = {'message' : "internal error"}
        return value, 503

@app.route(prefix+"/saes", methods=['POST'])
#@oidc.accept_token(True)
async def registerSAE(): 

    #roles = g.oidc_token_info['realm_access']['roles']
    #auth_ID = g.oidc_token_info['username']

    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if not any(r in roles for r in ['sae', 'admin']): 
        app.logger.info(f"registerSAE : rejected unauthorized user {auth_ID}")
        value =  {'message' : "ERROR: you are not an authorized SAE or ADMIN"}
        return value, 401

    content = await request.get_json()
    sae_ID = str(content['id'])
    if ('sae' in roles and auth_ID != sae_ID):
            value = {'message' : "ERROR: unauthorized, you can register only yourself!"}
            return value, 403
    
    try:
        status, value = await api.registerSAE(sae_ID) 
        if status:
            app.logger.info(f"registerSAE: completed for SAE {sae_ID}")
            return value, 200
        else:
            app.logger.warning(f"registerSAE: error for SAE {sae_ID} - message = {value['message']}")
            return value, 503
    except Exception as e: 
        app.logger.error(f"registerSAE EXCEPTION: {e}")
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/saes/<SAE_ID>", methods=['DELETE'])
#@oidc.accept_token(True)
async def unregisterSAE(SAE_ID): 

    #roles = g.oidc_token_info['realm_access']['roles']
    #auth_ID = g.oidc_token_info['username']

    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401


    if not any(r in roles for r in ['sae', 'admin']): 
        app.logger.info(f"unregisterSAE : rejected unauthorized user {auth_ID}")
        value =  {'message' : "ERROR: you are not an authorized SAE or ADMIN"}
        return value, 401

    SAE_ID = str(SAE_ID)
    if ('sae' in roles and auth_ID != SAE_ID):
            value = {'message' : "ERROR: unauthorized, you can unregister only yourself!"}
            return value, 403
    
    status, value = await api.unregisterSAE(SAE_ID) 
    if status: 
        app.logger.info(f"unregisterSAE: completed for SAE {SAE_ID}")
        return value, 200
    else: 
        app.logger.warning(f"unregisterSAE: error for SAE {SAE_ID} - message = {value['message']}")
        return value, 503


@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['POST'])
#@oidc.accept_token(True)
async def startQKDMStream(qkdm_ID) : 

    #roles = g.oidc_token_info['realm_access']['roles']
    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401
    
    if 'admin' not in roles: 
        app.logger.info(f"startQKDMStream : rejected unauthorized user {auth_ID}")
        value =  {'message' : "ERROR: you are not an authorized ADMIN"}
        return value, 401

    qkdm_ID = str(qkdm_ID)
    status, value = await api.startQKDMStream(qkdm_ID)
    if status: 
        app.logger.info(f"startQKDMStream: completed for qkdm {qkdm_ID}")
        return value, 200
    else: 
        app.logger.warning(f"startQKDMStream: completed for qkdm {qkdm_ID} - message = {value['message']}")
        return value, 503

@app.route(prefix+"/qkdms/<qkdm_ID>/streams", methods=['DELETE'])
#@oidc.accept_token(True)
async def deleteQKDMStreams(qkdm_ID) : 

    #roles = g.oidc_token_info['realm_access']['roles']
    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401
    
    if 'admin' not in roles:
        app.logger.info(f"deleteQKDMStreams : rejected unauthorized user {auth_ID}") 
        value =  {'message' : "ERROR: you are not an authorized ADMIN"}
        return value, 401

    qkdm_ID = str(qkdm_ID)
    status, value = await api.deleteQKDMStreams(qkdm_ID)
    if status: 
        app.logger.info(f"deleteQKDMStreams: completed for qkdm {qkdm_ID}")
        return value, 200
    else: 
        app.logger.warning(f"deleteQKDMStreams: completed for qkdm {qkdm_ID} - message = {value['message']}")
        return value, 503
    

@app.route(prefix+"/qks", methods=['POST'])
#@oidc.accept_token(True)
async def registerQKS(): 
    
    #roles = g.oidc_token_info['realm_access']['roles']
    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401
    
    if 'admin' not in roles:
        app.logger.info(f"deleteQKDMStreams : rejected unauthorized user {auth_ID}") 
        value =  {'message' : "ERROR: you are not an authorized ADMIN"}
        return value, 401
    
    content = await request.get_json()
    try:
        QKS_ID = str(content['QKS_ID'])
        QKS_IP = str(content['QKS_IP']) 
        QKS_port = int(content['QKS_port']) 
        routing_IP = str(content['routing_IP']) 
        routing_port = int(content['routing_port']) 

        
        status, value = await api.registerQKS(QKS_ID, QKS_IP, QKS_port, routing_IP, routing_port)
        if status: 
            app.logger.warning(f"registerQKS: completed for qks {QKS_ID}")
            return value, 200
        else: 
            app.logger.warning(f"registerQKS: error for qks {QKS_ID} - message = {value['message']}")
            return value, 503
    except Exception as e:
        app.logger.error(f"registerQKS EXCEPTION: {e}")
        value = {'message' : "error: invalid content"}
        return value, 400


# SOUTHBOUND INTERFACE 
@app.route(prefix+"/qkdms", methods=['POST'])
#@oidc.accept_token(True)
async def registerQKDM(): 

    #auth_ID = g.oidc_token_info['username']
    #roles = g.oidc_token_info['realm_access']['roles']
    
    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if not any(r in roles for r in ['qkdm', 'admin']): 
        app.logger.info(f"registerQKDM : rejected unauthorized user {auth_ID}") 
        value =  {'message' : "ERROR: you are not an authorized QKDM or ADMIN"}
        return value, 401


    content = await request.get_json()

    QKDM_ID = str(content['QKDM_ID']) if 'QKDM_ID' in content else None
    if QKDM_ID is None or ('qkdm' in roles and auth_ID != QKDM_ID):
        value = {'message' : "ERROR: unauthorized, you can register only yourself!"}
        return value, 403

    try:
        protocol = str(content['protocol']) 
        QKDM_IP = str(content['QKDM_IP']) 
        QKDM_port = int(content['QKDM_port']) 
        reachable_qks = str(content['reachable_QKS'])
        reachable_qkdm = str(content['reachable_QKDM']) 
        max_key_count = int(content['max_key_count']) 
        key_size = int(content['key_size']) 
        
        status, value = await api.registerQKDM(QKDM_ID, protocol, QKDM_IP, QKDM_port, reachable_qkdm, reachable_qks, max_key_count, key_size)
        if status: 
            app.logger.warning(f"registerQKDM: completed for qkdm_ID = {QKDM_ID}")
            return value, 200
        else: 
            app.logger.warning(f"registerQKDM: error for qkdm_ID = {QKDM_ID} - message = {value['message']}")
            return value, 503
    except Exception as e:
        app.logger.error(f"registerQKDM EXCEPTION: {e}")
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/qkdms/<qkdm_ID>", methods=['DELETE'])
#@oidc.accept_token(True)
async def unregisterQKDM(qkdm_ID): 

    #roles = g.oidc_token_info['realm_access']['roles']
    #auth_ID = g.oidc_token_info['username']

    header = request.headers.get('Authorization')
    res, auth_ID, roles = await verifyToken(header) 
    
    if not res: 
        value = {'message' : "ERROR: invalid Authorization header token"}
        return value, 401

    if not any(r in roles for r in ['qkdm', 'admin']): 
        app.logger.info(f"registerQKDM : rejected unauthorized user {auth_ID}")
        value =  {'message' : "ERROR: you are not an authorized QKDM or ADMIN"}
        return value, 401

    qkdm_ID = str(qkdm_ID)
    if ('qkdm' in roles and auth_ID != qkdm_ID) : 
        value = {'message' : "ERROR: unauthorized, you can unregister only yourself!"}
        return value, 403

    status, value = await api.unregisterQKDM(qkdm_ID) 
    if status: 
        app.logger.warning(f"unregisterQKDM: completed for qkdm_ID = {qkdm_ID}")
        return value, 200
    else: 
        app.logger.warning(f"unregisterQKDM: error for qkdm_ID = {qkdm_ID} - message = {value['message']}")
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
            app.logger.info(f"reserveKeys: completed for key_stream_ID = {key_stream_ID}")
            return value, 200
        else: 
            app.logger.warning(f"reserveKeys: error for key_stream_ID = {key_stream_ID} - message = {value['message']}")
            return value, 503
    except Exception as e: 
        app.logger.error(f"reserveKeys EXCEPTION: {e}")
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/forward", methods=['POST'])   
async def forwardData(): 
    content = await request.get_json()
    try:
        data = str(content['data'])
        decryption_key_ID = content['decryption_key_ID']
        decryption_stream_ID = str(content['decryption_stream_ID'])
        iv = str(content['iv'])
        destination_sae = str(content['destination_sae']) 
        
        status, value = await api.forwardData(data, decryption_key_ID, decryption_stream_ID, iv, destination_sae) 
        if status: 
            app.logger.info(f"forwardData: completed for destination_sae = {destination_sae}")
            return value, 200 
        else: 
            app.logger.warning(f"forwardData: error for destination_sae = {destination_sae} - message = {value['message']}")
            return value, 503 
    except Exception as e: 
        app.logger.error(f"forwardData EXCEPTION: {traceback.format_exc()}")
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route(prefix+"/streams", methods=['POST'])
async def createStream(): 
    content = await request.get_json()
    try:
        source_qks_ID = str(content['source_qks_ID'])
        key_stream_ID = str(content['key_stream_ID'])
        qkdm_id = str(content['qkdm_id']) if 'qkdm_id' in content else None

        status, value = await api.createStream(source_qks_ID, key_stream_ID, qkdm_id)
        if status: 
            app.logger.info(f"createStream: completed for key_stream_ID = {key_stream_ID}")
            return value, 200
        else: 
            app.logger.warning(f"createStream: error for key_stream_ID = {key_stream_ID} - message = {value['message']}")
            return value, 503
    except Exception as e:
        app.logger.error(f"createStream EXCEPTION: {e}")
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
            app.logger.info(f"closeStream: completed for key_stream_ID = {key_stream_ID}")
            return value, 200
        else: 
            app.logger.warning(f"closeStream: error for key_stream_ID = {key_stream_ID} - message = {value['message']}")
            return value, 503

    except Exception as e: 
        app.logger.error(f"closeStream EXCEPTION: {e}")
        value = {'message' : "error: invalid content"}
        return value, 400

@app.route("/test", methods=['POST'])
async def test(): 
    app.logger.warning(f"test EXECUTED")
    header = request.headers.get('Authorization')
    res, username, roles = await verifyToken(header)
    
    if res: 
        val = {'user' : username, 'roles' : roles}
        return val, 200
    else: 
        return {"message": "Invalid Token"}, 401
    

async def main() : 
    global app, serverPort, http_client, keycloak_data

    http_client = aiohttp.ClientSession()

    # check db and vault init 
    if len(sys.argv) == 2:
        status, serverPort, keycloak_data = await api.init_server(sys.argv[1])
    else: 
        status, serverPort, keycloak_data = await api.init_server()
    if not status: 
        app.logger.error(f"ERROR: unable to init DB, Vault or Redis")
        return  

    app.run(host='0.0.0.0', port=serverPort, loop = asyncio.get_event_loop())


if __name__ == "__main__":
	asyncio.run(main())
