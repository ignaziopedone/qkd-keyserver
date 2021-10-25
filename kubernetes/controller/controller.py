import kopf 
import logging
import kubernetes 

logger = logging.getLogger('controller')

def login(username) -> str : 
    # perform login 
    token = ""
    return token 

def getKey(slave_SAE_ID, number, size) -> dict : 
    # call getKey on the qks 
    return {}

def getKeyWithKeyIDs(master_SAE_ID:str, ids:list) -> dict : 
    # call getKeyWithKeyIDs on the qks 
    return {} 

def createSecret(namespace: str, key_data: dict) -> str:
    api_instance = kubernetes.client.CoreV1Api()
    data = {'data' : key_data}
    return api_instance.create_namespaced_secret(namespace, data)
    

@kopf.on.create('qks.controller', 'v1', 'keyrequests')
def keyreq_on_create(namespace, spec, body, **kwargs):
    logger.warning(f"A key request object has been created: {body}")

    try: 
        master_SAE_ID = spec['master_SAE_ID']
        slave_SAE_ID = spec['slave_SAE_ID']
    except Exception as e: 
        return {"error" : f"missing SAE ID {e}"}
    number = spec['number'] if 'number' in spec else None 
    size = spec['size'] if 'size' in spec else None 
    ids = spec['ids'] if 'ids' in spec else None 

    
    example_data = {
        'keys' : [
            {'key_ID' : 'exampleid1', 'key' : 'examplekey1'},
            {'key_ID' : 'exampleid2', 'key' : 'examplekey2'}
        ]
    }

    
    print(f"master_SAE: {master_SAE_ID}, slave_SAE: {slave_SAE_ID}")
    if ids is None: 
        logger.warning(f"request for getKey - number: {number}, size: {size}")
        token = login(master_SAE_ID)
        # authenticate retrieving master_SAE token from keycloak
        # require to the QKS the keys calling getKey
        
    else: 
        logger.warning(f"request for a getKeyWithKeyIDs - IDs: {ids}")
        token = login(slave_SAE_ID)
        # authenticate retrieving slave_SAE token from keycloak
        # require to the QKS the keys calling getKeyWithKeyIDs
        
    ret_data = example_data 
    secret_data = [{obj['key_ID'] : obj['key']} for obj in ret_data['keys']]
    secret = createSecret(namespace, secret_data)
    logger.warning(f"created secret with name: {secret.metadata.name}")
    return {"secret-name" : secret.metadata.name}
        
@kopf.on.create('qks.controller', 'v1', 'saes')
def sae_on_create(namespace, spec, body, **kwargs): 
    # if registration not manual try register to keycloak (check get_userinfo to know if already registered)
    # then register to QKS  
    return

@kopf.on.delete('qks.controller', 'v1', 'saes')
def sae_on_delete(namespace, spec, body, **kwargs):
    # unregister from QKS 
    return 