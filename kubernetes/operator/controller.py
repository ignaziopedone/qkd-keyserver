import kopf 
import logging
import kubernetes 
import base64
import requests
from uuid import uuid4 
import os 

logger = logging.getLogger('controller')

def login(username:str, namespace:str=None, admin:bool=False) -> str :  
    api_instance = kubernetes.client.CoreV1Api()
    secret_namespace = os.environ['SECRET_NAMESPACE']
    try: 
        if not admin: 
            credential_secret = api_instance.read_namespaced_secret(f"{username}-credentials", "default").data
            username = base64.b64decode(credential_secret["username"]).decode()
            password = base64.b64decode(credential_secret["password"]).decode()
            client_secret = api_instance.read_namespaced_secret(f"keycloak-secret", secret_namespace).data
            client_id = base64.b64decode(client_secret["client_id"]).decode()
            client_secret = base64.b64decode(client_secret["client_secret"]).decode()
            data = f"client_id={client_id}&client_secret={client_secret}&grant_type=password&scope=openid&username={username}&password={password}"
            realm = "qks"
        else: 
            credential_secret = api_instance.read_namespaced_secret(f"keycloak-secret", secret_namespace).data
            username = base64.b64decode(credential_secret["keycloak-user"]).decode()
            password = base64.b64decode(credential_secret["keycloak-password"]).decode()
            data = f"client_id=admin-cli&grant_type=password&scope=openid&username={username}&password={password}"
            realm = "master"

        header = {'Content-Type':'application/x-www-form-urlencoded'}  
        x = requests.post(f'http://keycloak-service:8080/auth/realms/{realm}/protocol/openid-connect/token', data=data, headers=header)
        token = x.json()['access_token']
    # perform login 
    except Exception as e: 
        logger.error(f"Login error: impossible to authenticate user {username} - {e}")
        token = None
    return token 

def createKeycloakUser(username:str) -> dict : 
    token = login("admin", admin=True)
    auth_header= {'Authorization' : f"Bearer {token}"}
    pwd = str(uuid4()).replace("-","")[:12]
    req_data = {
        "username": username,
        "enabled": True,
        "credentials": [{"value": pwd,"type": "password",}], 
        "realmRoles" : ["2593bed0-1f88-45d9-9fb1-bf21e49bbbe4"],
        "id" : username}

    
    req_user = requests.post("http://keycloak-service:8080/auth/admin/realms/qks/users", json=req_data, headers=auth_header)
    if req_user.status_code != 201 : 
        return None 

    users = requests.get(f"http://keycloak-service:8080/auth/admin/realms/qks/users?search={username}", headers=auth_header).json() 
    user_id = next((user["id"] for user in users if user["username"] == username), None)
    
    if user_id is None: 
        return None

    role_data = [{"id": "2593bed0-1f88-45d9-9fb1-bf21e49bbbe4", "name" : "sae"}] # sae role id 
    req_role = requests.post(f"http://keycloak-service:8080/auth/admin/realms/qks/users/{user_id}/role-mappings/realm", json=role_data, headers=auth_header)

    if req_role.status_code != 204: 
        return None 

    return {"username" : username, "password" : pwd}


def getKey(slave_SAE_ID:str, number:int, size:int, token:str) -> list : 
    auth_header= {'Authorization' : f"Bearer {token}"}
    # require keys calling getKey
    req_data = {"size" : size, "number" : number}
    req = requests.post(f'http://qks-service:4000/api/v1/keys/{slave_SAE_ID}/enc_keys', json=req_data, headers=auth_header)
    if req.status_code != 200 : 
        return []
    return req.json()['keys']

def getKeyWithKeyIDs(master_SAE_ID:str, ids:list, token:str) -> list : 
    auth_header= {'Authorization' : f"Bearer {token}"}
    # require keys calling getKeyWithKeyIDs
    req_data = {"key_IDs" : ids}
    req = requests.post(f'http://qks-service:4000/api/v1/keys/{master_SAE_ID}/dec_keys', json=req_data, headers=auth_header)
    if req.status_code != 200 : 
        return []
    return req.json()['keys'] 

def registerSAEtoQKS(sae_ID:str, token:str) -> bool : 
    auth_header= {'Authorization' : f"Bearer {token}"}
    req_data = {"id" : sae_ID}
    req = requests.post(f'http://qks-service:4000/api/v1/saes', json=req_data, headers=auth_header)
    if req.status_code != 200 : 
        logger.error(f"error in registerSAEtoQKS: {req.status_code}")
        return False
    return True 

def unregisterSAEfromQKS(sae_ID:str, token:str) -> bool: 
    auth_header= {'Authorization' : f"Bearer {token}"}
    req = requests.delete(f'http://qks-service:4000/api/v1/saes/{sae_ID}', headers=auth_header)
    if req.status_code != 200 : 
        logger.error(f"error in unregisterSAEfromQKS: {req.status_code}")
        return False
    return True 

def createSecret(namespace: str, key_data: dict, name:str) -> str:
    api_instance = kubernetes.client.CoreV1Api()
    for key, val in key_data.items(): 
        key_data[key] = base64.b64encode(val.encode()).decode()
    data = {'data' : key_data}
    data['metadata'] = {'name' : name}
    return api_instance.create_namespaced_secret(namespace, data)
    

@kopf.on.create('qks.controller', 'v1', 'keyrequests')
def keyreq_on_create(namespace, spec, body, name, **kwargs):
    logger.warning(f"A key request object has been created: {name}")

    cr_name = name
    try: 
        master_SAE_ID = spec['master_SAE_ID']
        slave_SAE_ID = spec['slave_SAE_ID']
    except Exception as e: 
        return {"error" : f"missing SAE ID - {e}"}
    number = spec['number'] if 'number' in spec else None 
    size = spec['size'] if 'size' in spec else None 
    ids = spec['ids'] if 'ids' in spec else None 
    
    logger.info(f"master_SAE: {master_SAE_ID}, slave_SAE: {slave_SAE_ID}")
    if ids is None: # getKey
        logger.info(f"request for getKey - number: {number}, size: {size}")
        token = login(master_SAE_ID, namespace=namespace) # authenticate retrieving master_SAE token from keycloak
        if token is None: 
            return {"message" : "ERROR in login"}

        ret_data = getKey(slave_SAE_ID, number, size, token)

    else: #getKeyWithKeyIDs
        logger.info(f"request for a getKeyWithKeyIDs - IDs: {ids}")
        token = login(slave_SAE_ID, namespace=namespace) # authenticate retrieving slave_SAE token from keycloak
        if token is None: 
            return {"message" : "ERROR in login"}
        
        ret_data = getKeyWithKeyIDs(master_SAE_ID, ids, token)
 
    secret_data = {}
    for el in ret_data: 
        secret_data[el['key_ID']] = el['key']
    secret = createSecret(namespace, secret_data, cr_name)
    logger.warning(f"created secret with name: {secret.metadata.name}")
    return {"secret-name" : secret.metadata.name}
        
@kopf.on.create('qks.controller', 'v1', 'saes')
def sae_on_create(namespace, spec, body, name, **kwargs): 
    # if registration not manual try register to keycloak 
    logger.warning(f"A sae object has been created: {name}")
    sae_id = spec['id'] 
    registration_auto = spec['registration_auto']

    if registration_auto is True: 
        ## register to keycloack 
        res = createKeycloakUser(sae_id)
        if res is None: 
            return {"message" : "ERROR in keycloak user creation "}
        
        createSecret(namespace, res, f"{sae_id}-credentials")
    
    # then register to QKS   
    token = login(sae_id, namespace=namespace)
    if token is None: 
        return {"message" : "ERROR in login"} 

    if registerSAEtoQKS(sae_id, token): 
        logger.warning(f"registered sae with id: {sae_id}")
        return {"message" : "SAE registered successfully"}
    else:
        logger.warning(f"ERROR in registering sae with id: {sae_id}") 
        return {"message" : "ERROR in sae registration to QKS"}    

@kopf.on.delete('qks.controller', 'v1', 'saes')
def sae_on_delete(namespace, spec, body, name, **kwargs):
    logger.warning(f"A sae object has been deleted: {name}")
     
    sae_id = spec['id']
    # unregister from QKS 
    token = login(sae_id, namespace=namespace)
    if token is None: 
        return {"message" : "ERROR in login"} 
    
    if unregisterSAEfromQKS(sae_id, token): 
        logger.warning(f"unregistered sae with id: {sae_id}")
        return {"message" : "SAE removed successfully"}
    else: 
        logger.warning(f"ERROR in unregistering sae with id: {sae_id}") 
        return {"message" : "ERROR in sae removal from QKS"}