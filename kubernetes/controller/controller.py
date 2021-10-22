import kopf 
import logging
import kubernetes 
import base64
import requests

example_data = {
    'keys' : [
        {'key_ID' : 'exampleid1', 'key' : 'examplekey1'},
        {'key_ID' : 'exampleid2', 'key' : 'examplekey2'}
    ]
}

logger = logging.getLogger('controller')
client_id = 'test'



def login(username) -> str : 

    api_instance = kubernetes.client.CoreV1Api()
    credential_secret = api_instance.read_namespaced_secret(f"{username}-credentials", "default").data
    username = base64.b64decode(credential_secret["username"])
    password = base64.b64decode(credential_secret["password"])

    client_secret = api_instance.read_namespaced_secret(f"qksclient-secret", "default").data
    client_id = base64.b64decode(client_secret["client_id"])
    client_secret = base64.b64decode(credential_secret["client_secret"])

    header = {'Content-Type':'application/x-www-form-urlencoded'} 
    data = f"client_id={client_id}&client_secret={client_secret}&grant_type=password&scope=openid&username={username}&password={password}"
    try: 
        x = requests.post('http://keycloak-service:8080/auth/realms/qks/protocol/openid-connect/token', data=data, headers=header)
        token = x.json()['access_token']
    # perform login 
    except Exception as e: 
        logger.error(f"Login error: impossible to authenticate user {username}")
        token = None
    return token 

def getKey(slave_SAE_ID:str, number:int, size:int, token:str) -> list : 
    auth_header= {'Autorization' : f"Bearer {token}"}
    # require keys calling getKey
    req_data = {"size" : size, "number" : number}
    req = requests.post(f'http://qks-service/api/v1/keys/{slave_SAE_ID}/enc_keys', json=req_data, headers=auth_header)
    if req.status_code != 200 : 
        return {"message" : "unable to retrieve key, QKS error"}
    return req.json()['keys']

def getKeyWithKeyIDs(master_SAE_ID:str, ids:list, token:str) -> list : 
    auth_header= {'Autorization' : f"Bearer {token}"}
    # require keys calling getKeyWithKeyIDs
    req_data = {"key_IDs" : ids}
    req = requests.post(f'http://qks-service/api/v1/keys/{master_SAE_ID}/dec_keys', json=req_data, headers=auth_header)
    if x.status_code != 200 : 
        return {"message" : "unable to retrieve key. QKS error"}
    return req.json()['keys'] 

def createSecret(namespace: str, key_data: dict, name:str) -> str:
    api_instance = kubernetes.client.CoreV1Api()
    for key, val in key_data.items(): 
        key_data[key] = base64.b64encode(val.encode()).decode()
    data = {'data' : key_data}
    data['metadata'] = {'name' : name}
    return api_instance.create_namespaced_secret(namespace, data)
    

@kopf.on.create('qks.controller', 'v1', 'keyrequests')
def on_create(namespace, spec, body, name, **kwargs):
    global logger 
    logger.warning(f"A key request object has been created: {body}")

    cr_name = name
    try: 
        master_SAE_ID = spec['master_SAE_ID']
        slave_SAE_ID = spec['slave_SAE_ID']
    except Exception as e: 
        return {"error" : f"missing SAE ID {e}"}
    number = spec['number'] if 'number' in spec else None 
    size = spec['size'] if 'size' in spec else None 
    ids = spec['ids'] if 'ids' in spec else None 
    
    logger.info(f"master_SAE: {master_SAE_ID}, slave_SAE: {slave_SAE_ID}")
    if ids is None: # getKey
        logger.info(f"request for getKey - number: {number}, size: {size}")
        token = login(master_SAE_ID) # authenticate retrieving master_SAE token from keycloak
        if token is None: 
            return {"message" : "ERROR in login"}

        ret_data = getKey(slave_SAE_ID, number, size, token)

    else: #getKeyWithKeyIDs
        logger.info(f"request for a getKeyWithKeyIDs - IDs: {ids}")
        token = login(slave_SAE_ID) # authenticate retrieving slave_SAE token from keycloak
        if token is None: 
            return {"message" : "ERROR in login"}
        
        ret_data = getKeyWithKeyIDs(master_SAE_ID, ids, token)
 
    secret_data = {}
    for el in ret_data['keys']: 
        secret_data[el['key_ID']] = el['key']
    secret = createSecret(namespace, secret_data, cr_name)
    logger.warning(f"created secret with name: {secret.metadata.name}")
    return {"secret-name" : secret.metadata.name}
        
