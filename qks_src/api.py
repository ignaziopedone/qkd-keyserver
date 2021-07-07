from aioredis.client import Redis
import yaml
from math import ceil
from uuid import uuid4
from base64 import b64decode, b64encode

from asyncVaultClient import VaultClient # from VaultClient import VaultClient 
import aiohttp #import requests
from motor.motor_asyncio import AsyncIOMotorClient as MongoClient # from pymongo import MongoClient, ReturnDocument
import aioredis

config_file = open("qks_src/config_files/config.yaml", 'r')
config : dict = yaml.safe_load(config_file)
config_file.close()

mongo_client : MongoClient = None # once it has been initialized all APIs use the same client
vault_client : VaultClient = None 
redis_client : Redis = None
http_client : aiohttp.ClientSession = None


# NORTHBOUND 
async def getStatus(slave_SAE_ID : str, master_SAE_ID : str) -> tuple[bool, dict] : 
    global mongo_client, http_client, redis_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    master_sae_rt = await redis_client.hgetall(master_SAE_ID) #me = await qks_collection.find_one({"_id" : config['qks']['id']})
    if not master_sae_rt or master_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)

    sae_rt = await redis_client.hgetall(slave_SAE_ID) #dest_qks = await qks_collection.find_one({ "connected_sae": slave_SAE_ID }) 
    # if slave_SAE is present in this qkd network
    if sae_rt : #is not None:  -> check if the returned dict is not empty 
        if sae_rt['dest'] == config['qks']['id']: 
            status = {"message" : f"ERROR: {slave_SAE_ID} registered on this host"}
            return (False, status)
        
        
        res = {
            'source_KME_ID': config['qks']['id'],
            'target_KME_ID': sae_rt['dest'], # dest_qks['_id'],
            'master_SAE_ID': master_SAE_ID,
            'slave_SAE_ID': slave_SAE_ID,
            'max_key_per_request': int(config['qks']['max_key_per_request']),
            'max_key_size': int(config['qks']['max_key_size']),
            'min_key_size': int(config['qks']['min_key_size']),
            'max_SAE_ID_count': 0
        }

        res['connection_type'] = "direct"

        qkdm_exist = True if res['connection_type'] == "direct" else False 
        key_stream = await key_stream_collection.find_one({"dest_qks.id" : sae_rt['dest'], "qkdm" : {"$exists" : qkdm_exist}})
        
        if key_stream is not None:
            if qkdm_exist: 
                address = key_stream['qkdm']['address']
                
                
                async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{key_stream['_id']}") as ret: 
                    ret_val = await ret.json()
                    ret_status = ret_val['status']
                    if ret.status_code == 200 and ret_status == 0: 
                        res['stored_key_count'] = ret_val['available_indexes']
                    else: 
                        res['stored_key_count'] = 0

                res['key_size'] = key_stream['standard_key_size']
                res['max_key_count'] = key_stream['max_key_count']
                return (True, res )
            else: 
                #manage an indirect connection 
                status = {"message" : "ERROR: There should be an indirect stream but they are not yet implemented"}
                return (False, status)
        else: 
            # no stream available. Try to open an indirect connection
            status = {"message" : "ERROR: This sae is connected but is unreachable: no direct connections are available"}
            return (False, status)
 
    else : 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)   

async def getKey(slave_SAE_ID: str , master_SAE_ID : str, number : int =1, key_size : int = None, extensions = None ) -> tuple[bool, dict] :
    global mongo_client, http_client, redis_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    if key_size is None: 
        key_size = config['qks']['def_key_size'] 
    elif key_size > config['qks']['max_key_size'] or key_size < config['qks']['min_key_size'] or key_size % 8 != 0: 
        status = {"message" : "ERROR: please respect key size limits: check them with getStatus function. Size must be a multiple of 8"}
        return (False, status) 

    if number > config['qks']['max_key_per_request'] : 
        status = {"message" : "ERROR: please respect max_key_per_request limit: check it with getStatus function"}
        return (False, status) 


    master_sae_rt = await redis_client.hgetall(master_SAE_ID) #me = await qks_collection.find_one({"_id" : config['qks']['id']})
    if not master_sae_rt or master_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)

    if extensions is not None:
        if len(extensions) == 1 and 'require_direct' in extensions and type(extensions['require_direct'] ) is bool:
            required_direct = extensions['require_direct'] 
        else: 
            status = {"message" : "invalid extensions! The only supported extension is require_direct with boolean value"}
            return (False, status)
         

    slave_sae_rt = await redis_client.hgetall(master_SAE_ID)
    stream_type = "direct"

    if not slave_sae_rt : 
        status = {"message" : "ERROR: slave_SAE_ID not found on this network! "}
        return (False, status) 

    direct_stream = True if stream_type == "direct" else False 
    if direct_stream is False and required_direct is True: 
        status = {"message" : "ERROR: there are no direct connection available as required"}
        return (False, status)

    key_stream = await key_stream_collection.find_one({"dest_qks.id" : slave_sae_rt['dest'], "qkdm" : {"$exists" : direct_stream}})

    if key_stream is None: 
        status = {"message" : "ERROR: there are no streams to reach requeted SAE", 
                    "details" : "indirect connection not implemented yet. Call getStatus before getKey to avoid this error"}
        return (False, status)

    # check available keys and save their ids inside stream.reserved_keys collection 
    needed_keys = number
    list_to_be_sent = []
    used_AKIDs = []

    chunks_for_each_key = int(ceil(float(key_size) / key_stream['standard_key_size'])  ) 
    if 'qkdm' in key_stream:  
        address = key_stream['qkdm']['address']
        
        async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{key_stream['_id']}?count=-1") as ret: 
            ret_val = await ret.json()
            ret_status = ret_val['status']
            if ret.status == 200 and ret_status == 0: 
                kids = ret_val['available_indexes'] 
            else:
                status =  {"message" : "ERROR: qkdm unable to answer correctly "} 
                return (False, status )

        av_AKIDs = int(len(kids) / chunks_for_each_key)
        # RELAXED APPROACH : IF THERE ARE NOT ENOUGH AVAILABLE KEYS RETURN WHAT IS AVAILABLE
        
        start = 0
        for i in range(0, av_AKIDs): 
            AKID = str(uuid4() )
            AKID_kids = kids[start:(start + chunks_for_each_key)]
            start += chunks_for_each_key 
            # save reserved_keys_for_this_stream in the DB stream collection (reservedKeys)
            # we suppose that generated uuid are unique, no need to check their uniqueness
            element  = {'AKID' : AKID, 'sae' : slave_SAE_ID, 'kids' : AKID_kids}  
            query =  {"_id" : key_stream['_id'], "reserved_keys" : {
                "$not" : {
                    "$elemMatch" :  {"kids" : {"$in" : AKID_kids}}
                }        
            }}
 
            update = {"$push" : {"reserved_keys" : element}}
            res = await key_stream_collection.update_one(query, update)
            if res.modified_count == 1: 
                    needed_keys -= 1
                    list_to_be_sent.append({'AKID' : AKID, 'kids' : AKID_kids})
                    used_AKIDs.append(AKID)
            
            if needed_keys == 0: 
                break 
    else: 
        # indirect stream not implemented yet
        status =  {"message" : "ERROR: indirect stream not implemented yet"} 
        return (False, status )

    if len(list_to_be_sent) < 1 : 
        status =  {"message" : "ERROR: unable to reserve any key"} 
        return (False, status )


    # send reserveKey(list_to_be_sent) requests to the peer qks
    post_data = {
        "key_stream_ID" : key_stream['_id'],
        "slave_SAE_ID" : slave_SAE_ID, 
        "key_size" : key_size,
        "key_ID_list" : list_to_be_sent
    }
    dest_qks_ip = key_stream['dest_qks']['address']['ip']
    dest_qks_port = int(key_stream['dest_qks']['address']['port'])
    async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/keys/{master_SAE_ID}/reserve", json=post_data) as response:
        if response.status != 200: 
            status = {"message" : "ERROR: peer qks unable to reserve keys", 
            "peer_message" : str(await response.text)}
            await key_stream_collection.update_one({"_id" : key_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : {"$in" : used_AKIDs}}}})
            return (False, status)

    res = {'keys' : [], 'key_container_extension' : {'direct_communication' : direct_stream, 'returned_keys' : len(list_to_be_sent)}}
    for element in list_to_be_sent: 
        AKID = element['AKID']
        kids = element['kids']
        if 'qkdm' in key_stream: 
            address = key_stream['qkdm']['address']
            post_data = {'key_stream_ID' : key_stream['_id'], 'indexes' : kids}
            async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_key", json=post_data) as ret: 
                ret_val = await ret.json()
                ret_status_code = ret.status()
        else: 
            status = {"message" : "ERROR: there was a request for an indirect stream which are not supported yet"}
            return (False, status)
        ret_status = ret_val['status']
        if ret_status != 0 or ret_status_code != 200: 
            status = {"message" : "ABORT : THIS SHOULD NOT HAPPEN! there is someone else which is not this QKS that is using the QKDM!"}
            return (False, status)
        chunks = ret_val['keys']
        
        byte_key = b''
        for el in chunks :
            byte_key += b64decode(el.encode()) 
        key = b64encode(byte_key[0:(key_size//8)]).decode()
        res['keys'].append({'key_ID' : AKID, 'key' : key}) # key joined as bytearray, return as b64 string 
        
    await key_stream_collection.update_one({"_id" : key_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : {"$in" : used_AKIDs}}}})
    return (True, res)
        
async def getKeyWithKeyIDs(master_SAE_ID: str, key_IDs:list, slave_SAE_ID:str) -> tuple[bool, dict] :
    # REDIS saves 1 over 3 db query  
    global mongo_client, config, http_client, redis_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    # check that slave_SAE is registered to this qks
    slave_sae_rt = await redis_client.hgetall(slave_SAE_ID) 
    if not slave_sae_rt or slave_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)
    
    if len(key_IDs) > config['qks']['max_key_per_request']: 
        status = {"message" : f"ERROR: number of key per request limited to { config['qks']['max_key_per_request']}"}
        return (False, status)   

    # get all streams that have a reserved_key matching one of the requested one
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    query = {"reserved_keys" : {"$elemMatch" : {"sae" : master_SAE_ID, "AKID" : {"$in" : key_IDs}}}}
    cursor = stream_collection.find(query)
    matching_streams = await cursor.to_list()

    # if no key available signal it 
    if matching_streams.count() == 0:
        status = {"message" : "none of your requester keys are available!"}
        return (False, status)

    keys_to_be_returned = { 'keys' : []}
    for key_stream in matching_streams:
        for key in key_stream['reserved_keys']:
            if key['AKID'] in key_IDs and key['sae'] == master_SAE_ID:
                # for each requested AKID require all its chunks and build the aggregate key
                if 'qkdm' in key_stream: 
                    address = key_stream['qkdm']['address']
                    post_data = {'key_stream_ID' : key_stream["_id"], 'indexes' : key['kids']}
                    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_key", json=post_data) as ret:
                        ret_val = await ret.json()
                        ret_status = ret_val['status']
                        returned_keys = ret_val['keys'] if ret_status == 0 else None 
                        ret_status_code = ret.status
                
                else: 
                    status = {"message" : "Some keys belong to an indirect stream which is not supported yet"}
                    return (False, status)

                if ret_status == 0 and ret_status_code == 200: 
                    # if a key is not available in the module it won't be returned but the other keys will be returned correctly
                    byte_key = b''
                    for el in returned_keys :
                        byte_key += b64decode(el.encode()) 
                    aggregate_key = b64encode(byte_key[0:(key['key_size']//8)]).decode()
                    keys_to_be_returned['keys'].append({'key_ID' : key['AKID'], 'key' : aggregate_key})

                    # remove akid from reserved keys
                    await stream_collection.update_one({"_id" : key_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : key['AKID']}}})
    return (True, keys_to_be_returned)

async def getQKDMs() -> tuple[bool, dict]: 
    # return the whole qkdm collection
    global mongo_client, config
    qkdms_collection = mongo_client[config['mongo_db']['db']]['qkd_modules']
    qkdm_list = qkdms_collection.find()
    mod_list = []
    async for qkdm in qkdm_list:  
        mod_list.append(qkdm)
    qkdms = {'QKDM_list' : mod_list}
    return (True, qkdms)

async def registerSAE(sae_ID: str) -> tuple[bool, dict]: 
    global mongo_client, config, redis_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    sae_rt = await redis_client.hgetall(sae_ID) #me = await qks_collection.find_one({"_id" : config['qks']['id']})
    if sae_rt :
        value = {"message" : "ERROR: this SAE is already registered in this network"}
        return (False, value)
    else : 
        res = await qks_collection.update_one({ "_id": config['qks']['id'] }, { "$addToSet": { "connected_sae": sae_ID  }})
        value = {"message" : "SAE successfully registered to this server"} 
        await redis_client.publish(f"{config['redis']['topic']}-sae", f"add-{sae_ID}")
        return (True, value)

async def unregisterSAE(sae_ID: str) -> tuple[bool, dict]: 
    global mongo_client, config, redis_client
    qks_collection = await mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    sae_rt = await redis_client.hgetall(sae_ID)
    if not sae_rt or sae_rt['dest'] != config['qks']['id']: 
        value = {"message" : "ERROR: this SAE is NOT registered to this server"}
        return (False, value)
    else : 
        res = await qks_collection.update_one({ "_id": config['qks']['id'] }, { "$pull": { "connected_sae": sae_ID  }})
        await redis_client.publish(f"{config['redis']['topic']}-sae", f"remove-{sae_ID}")
        value = {"message" : "SAE successfully removed from this server"}
        return (True, value) 

# TODO
async def getPreferences() : 
    preferences = {}
    return preferences

# TODO
async def setPreference(preference:str, value) : 
    return 

async def startQKDMStream(qkdm_ID:str) -> tuple[bool, dict] : 
    global mongo_client, config, http_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']  
    qkdm_collection = mongo_client[config['mongo_db']['db']]['qkd_modules']  
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams'] 
    

    qkdm = await qkdm_collection.find_one({"_id" : qkdm_ID})
    if qkdm is None: 
        status = {"message" : "ERROR: this qkdm is not registered on this host! "}
        return (False, status)

    qkdm_stream = await key_stream_collection.find_one({"dest_qks.id" : qkdm['reachable_qks'],  "qkdm" : {"$exists" : True}})
    if qkdm_stream is not None: 
        status = {"message" : "ERROR: there is already an active direct stream to this destination. This QKS version only allows 1 direct stream between each QKS couple"}
        return (False, status)
    
    dest_qks = await qks_collection.find_one({"_id" : qkdm['reachable_qks']})
    address = qkdm['address']
    post_data = {'source' : config['qks']['id'], 'destination' : dest_qks['_id']} 
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/open_connect", json=post_data) as ret: 
        data = await ret.json()
        ret_status = data['status']
        key_stream_ID = data['key_stream_ID'] if ret_status == 0 else None
        
        if ret_status != 0 or ret.status != 200: 
            status = {"message" : "ERROR: QKDM unable to open the stream"}
            return (False, status)
            
    post_data = {
        'qkdm_id' : qkdm['reachable_qkdm'],
        'source_qks_ID' : config['qks']['id'],
        'type' : "direct",
        'key_stream_ID' : key_stream_ID
    }

    # call createStream on the peer qks 

    dest_qks_ip = dest_qks['address']['ip']
    dest_qks_port = int(dest_qks['address']['port']) 
    async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/streams", json=post_data) as response:
        if response.status != 200 :
            status = {"message" : "ERROR: peer QKS unable to create the stream"}
            return (False, status)
    
    # everything ok: insert the stream in the db 
    in_qkdm = {"id" : qkdm['_id'], "address" : qkdm['address']}
    in_qks = {"id" :  dest_qks['_id'], "address" : dest_qks['address']}
    key_stream = {"_id" : key_stream_ID, 
        "dest_qks" : in_qks, 
        "standard_key_size" : qkdm['parameters']['standard_key_size'], 
        "max_key_count" : qkdm['parameters']['max_key_count'],
        "reserved_keys" : [], 
        "qkdm" : in_qkdm
    }
    await key_stream_collection.insert_one(key_stream)
    await redis_client.publish(f"{config['redis']['topic']}-link", f"add-{dest_qks['_id']}")
    status = {"message" : f"OK: stream {key_stream_ID} started successfully"}
    return (True, status)
        
async def deleteQKDMStreams(qkdm_ID:str) -> tuple[bool, dict] : 
    global mongo_client, config, http_client, redis_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams'] 
    
    key_stream = await key_stream_collection.find_one({"qkdm.id" : qkdm_ID})
    if key_stream is None: 
        status = {"message" : "There are no active stream for this QKDM on this host "}
        return (False, status)
    key_stream_ID = key_stream["_id"]
        
    delete_data = {
        'source_qks_ID' : config['qks']['id'],
        'key_stream_ID' : key_stream_ID
    }

    # call closeStream on the peer qks 
    dest_qks_ip = key_stream['dest_qks']['address']['ip']
    dest_qks_port = int(key_stream['dest_qks']['address']['port'])
    async with http_client.delete(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/streams/{key_stream_ID}", json=delete_data) as response:
        if response.status != 200 :
            status = {"message" : "ERROR: peer QKS unable to close the stream", 
            "peer_message" : (await response.text)}
            return (False, status)
    
    address = key_stream['qkdm']['address']
    post_data = {'key_stream_ID' : key_stream_ID} 
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/close", json=post_data) as ret: 
        ret_val = await ret.json()
        ret_status = ret_val['status']
        await key_stream_collection.delete_one({"_id" : key_stream_ID})
        if ret_status == 0 and ret.status == 200:
            status = {"message" : f"OK: stream {key_stream_ID} closed successfully"}
        else: 
            status = {"message" : f"FORCED CLOSURE: stream {key_stream_ID} closed by peer, qkdm is unable to close it but this ID is not valid anymore"}
        await redis_client.publish(f"{config['redis']['topic']}-link", f"remove-{key_stream['dest_qks']['id']}")
        return (True, status)

async def registerQKS(qks_id:str, qks_ip:str, qks_port:int, routing_ip:str, routing_port:int): 
    global mongo_client, config
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    data = {
        "_id" : qks_id, 
        "connected_sae" : [], 
        "neighbor_qks" : [], 
        "address" : {"ip" : qks_ip, "port" : qks_port}, 
        "routing_address" : {"ip" : routing_ip, "port" : routing_port}
    } 

    res  = await qks_collection.update_one({"_id" : qks_id}, {"$setOnInsert" : data}, upsert=True)
    if res.matched_count == 1 :
        value = {"message" : "ERROR: this QKS is already registered in this network"}
        return (False, value)
    else : 
        value = {"message" : "QKS successfully registered on this network. Its information will be progragated after a qkdm link is established"} 
        await redis_client.publish(f"{config['redis']['topic']}-qks", f"add-{qks_id}_{routing_ip}_{routing_port}")
        return (True, value)


# SOUTHBOUND 
async def registerQKDM(qkdm_ID:str, protocol:str, qkdm_ip:str, qkdm_port:int, reachable_qkdm: str, reachable_qks:str, max_key_count:int, key_size:int) -> tuple[bool, dict]: 
    global mongo_client, vault_client, config
    qkdms_collection = mongo_client[config['mongo_db']['db']]['qkd_modules'] 
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    if qkdm_port < 0 or qkdm_port > 65535: 
        value = {'message' : "ERROR: invalid port number"}
        return (False, value)

    if (await qkdms_collection.find_one({"_id" : qkdm_ID})) is not None: 
        value = {'message' : "ERROR: this qkdm is already registered but retrieving known qkdm data is not supported yet"}
        return (False, value)

    if (await qks_collection.find_one({"_id" : reachable_qks})) is None: 
        value = {'message' : "ERROR: reachable qks is unknows, please register it on this network"}
        return (False, value)
    

    qkdm_data = {"_id" : qkdm_ID, 
                "address" : {"ip" : qkdm_ip, "port" : qkdm_port}, 
                "reachable_qkdm" : reachable_qkdm, 
                "reachable_qks" : reachable_qks, 
                "protocol" : protocol, 
                "parameters" : {"max_key_count" : max_key_count, "standard_key_size" : key_size}}


    res = await vault_client.createUser(qkdm_ID)
    if res is None : 
        value = {'message' : "ERROR: unable to create a user for you in Vault"}
        return (False, value)

    return_value = {}
    return_value['vault_data'] = {
        'host' : config['vault']['host'], 
        'port' : config['vault']['port'], 
        'secret_engine' : qkdm_ID, 
        'role_id' : res['role_id'], 
        'secret_id' : res['secret_id'] } 


    admin_db = mongo_client['admin'] 
    password = str(uuid4()).replace("-", "")
    username = qkdm_ID
    try: 
        await admin_db.command("createUser", username, pwd = password, roles =  [{ 'role': 'readWrite', 'db': qkdm_ID }] )
    except Exception: 
        value = {'message' : "ERROR: unable to create a user for you in database"}
        await vault_client.deleteUser(qkdm_ID)
        return (False, value)
    
    res = await qkdms_collection.insert_one(qkdm_data)
    return_value['database_data'] = {
        'host' : config['mongo_db']['host'], 
        'port' :  config['mongo_db']['port'], 
        'db_name' : qkdm_ID, 
        'username' : username, 
        'password' : password, 
        'auth_src' : config['mongo_db']['auth_src']}

    return (True, return_value)

async def unregisterQKDM(qkdm_ID:str) -> tuple[bool, dict]: 
    global mongo_client, vault_client, config
    qkdms_collection = mongo_client[config['mongo_db']['db']]['qkd_modules'] 
    
    if await qkdms_collection.find_one({"_id" : qkdm_ID}) is None: 
        value = {'message' : "ERROR: QKDM not found on this host"}
        return (False, value)


    res = await vault_client.deleteUser(qkdm_ID)
    if not res: 
        value = {'message' : "ERROR: unable to delete vault accesses"}
        return (False, value)

    admin_db = mongo_client['admin'] 
    await admin_db.command("dropUser", qkdm_ID)
    await mongo_client.drop_database(qkdm_ID)

    await qkdms_collection.delete_one({"_id" : qkdm_ID})
    

    value = {'message' : "QKDM removed successfully"}
    return (True, value) 

# EXTERNAL 
async def reserveKeys(master_SAE_ID:str, slave_SAE_ID:str, key_stream_ID:str, key_size:int, key_ID_list:list) -> tuple[bool, dict]: 
    global mongo_client, config, http_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']  
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    if (key_size > config['qks']['max_key_size']) or (key_size < config['qks']['min_key_size'] or key_size % 8 != 0) : 
        status = {"message" : "ERROR: requested key size doesn't match this host parameters. Use getStatus to get more information. Size must be a multiple of 8"}
        return (False, status)

    me = await qks_collection.find_one({"_id" : config['qks']['id'], "connected_sae" : slave_SAE_ID})
    if me is None: 
        status = {"message" : "ERROR: slave_SAE_ID not registered on this host"}
        return (False, status) 

    key_stream = await key_stream_collection.find_one({"_id" : key_stream_ID})
    if key_stream is None: 
        status = {"message" : "ERROR: invalid key_stream_ID"}
        return (False, status) 

    valid_list = True
    kids_to_be_checked = set()
    akids = set()
    for element in key_ID_list: 
        if not('AKID' in element and 'kids' in element and type(element['kids']) is list) or (key_stream['standard_key_size']*len(element['kids']) < key_size): 
            valid_list = False
            break
        else: 
            element['sae'] = master_SAE_ID
            element['key_size'] = key_size 
            kids_to_be_checked.update(list(element['kids']))
            akids.add(element['AKID'])

    if not valid_list: 
        status = {"message" : "ERROR: key_ID_list not properly formatted"}
        return (False, status)
    
    kids_per_akid = int(ceil(float(key_size) / key_stream['standard_key_size'])  ) 
    if (len(akids) != len(key_ID_list)) or len(kids_to_be_checked)!= len(akids)*kids_per_akid : 
        status = {"message" : "ERROR: there are some duplication in AKIDs or kids received"}
        return (False, status) 

    if 'qkdm' not in key_stream: 
        status = {"message" : "ERROR: indirect streams not supported yet"}
        return (False, status) 

    
    address = key_stream['qkdm']['address']
    post_data = {'key_stream_ID' : key_stream_ID, 'indexes' : list(kids_to_be_checked)} 
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/check_id", json=post_data) as ret: 
        ret_val = await ret.json()
        ret_status = ret_val['status']
        if ret.status!=200 or ret_status != 0:
            status = {"message" : "ERROR: some kids are not available! "}
            return (False, status)  

    query =  {"_id" : key_stream_ID, "reserved_keys" : {
        "$not" : {
            "$elemMatch" :  {"$or" : [
                {"AKID" : {"$in" : list(akids)}}, 
                {"kids" : {"$in" : list(kids_to_be_checked)}}]
            }
        } 
    }}
 
    update = {"$push" : {"reserved_keys" : {"$each" : key_ID_list}}}
    res = await key_stream_collection.update_one(query, update)
    if res.modified_count != 1:  
        status = {"message" : "ERROR: unable to reserve these keys due to AKID or kids duplication! "}
        return (False, status)
    else: 
        status = {"message" : "keys reserved correctly!  "}
        return (True, status)

# TODO
async def forwardData(data, decryption_key_id:str, decryption_key_stream:str): 
    return 

async def createStream(source_qks_ID:str, key_stream_ID:str, stream_type:str, qkdm_id:str=None) -> tuple[bool, dict]:
    global mongo_client, config, http_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    qkdm_collection = mongo_client[config['mongo_db']['db']]['qkd_modules']
    
    
    if stream_type == "indirect":
        # open an indirect stream 
        return (False, "ERROR: Indirect stream not implemented yet")

    elif stream_type == "direct" and qkdm_id:
        source_qks = await qks_collection.find_one({"_id" : source_qks_ID})
        if  source_qks is None or (await stream_collection.find_one({"_id": key_stream_ID }) is not None):
            value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
            return (False, value)
        
        selected_qkdm = await qkdm_collection.find_one({"_id" : qkdm_id})
        if  selected_qkdm is not None: 
            address = selected_qkdm['address']  
            post_data = {'key_stream_ID' : key_stream_ID, 'source' : source_qks_ID, 'destination' : config['qks']['id']} 
            async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/open_connect", json=post_data) as ret: 
                ret_val = await ret.json()
                ret_status = ret_val['status']
                if ret_status == 0 and ret.status == 200: 
                    in_qkdm = {"id" : selected_qkdm['_id'], "address" : selected_qkdm['address']}
                    dest_qks = {"id" : source_qks_ID, "address" : source_qks['address']}
                    new_stream = {"_id" : key_stream_ID, "dest_qks" : dest_qks, "reserved_keys" : [], "qkdm" : in_qkdm, "standard_key_size" : selected_qkdm['parameters']['standard_key_size'], "max_key_count" : selected_qkdm['parameters']['max_key_count']}
                    await stream_collection.insert_one(new_stream)
                    await redis_client.publish(f"{config['redis']['topic']}-link", f"add-{source_qks_ID}")
                    value = {'message' : "stream successfully created"}
                    return (True, value)
                else: 
                    value = {'message' : "ERROR in stream creation"}
                    return (False, value)

    else: 
        value = {'message' : "ERROR: invalid stream type or qkdm_id"}
        return (False, value)

async def closeStream(key_stream_ID:str, source_qks_ID:str) -> tuple[bool, dict]:
    global mongo_client, config, http_client
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    
    key_stream =  await stream_collection.find_one({"_id" : key_stream_ID, "dest_qks.id" : source_qks_ID}) 
    if key_stream is None:
        value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
        return (False, value)
    
    if 'qkdm' in key_stream : 
        address = key_stream['qkdm']['address']  
        post_data = {'key_stream_ID' : key_stream_ID} 
        async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/close", json=post_data) as ret:
            ret_val = await ret.json()
            ret_status = ret_val['status']
            if ret_status == 0 and ret.status == 200: 
                await stream_collection.delete_one({"_id" : key_stream_ID})
                await redis_client.publish(f"{config['redis']['topic']}-link", f"remove-{source_qks_ID}")
                value = {'message' : "stream successfully closed"}
                return (True, value)
            else: 
                value = {'message' : "ERROR in stream closure"}
                return (False, value)
    else: 
        # close indirect stream
        return (False, "not implemented yet") 


# MANAGEMENT FUNCTIONS
async def init_server() -> tuple[bool, int ] : 
    # check that the qks can access admin DB with root credentials  
    global mongo_client, vault_client, config, http_client, redis_client
    test_mongo_client = MongoClient(f"mongodb://{config['mongo_db']['user']}:{config['mongo_db']['password']}@{config['mongo_db']['host']}:{config['mongo_db']['port']}/admin?authSource={config['mongo_db']['auth_src']}")

    try: 
        await test_mongo_client.list_database_names()
        mongo_client = MongoClient(f"mongodb://{config['mongo_db']['user']}:{config['mongo_db']['password']}@{config['mongo_db']['host']}:{config['mongo_db']['port']}/{config['mongo_db']['db']}?authSource={config['mongo_db']['auth_src']}")
    except Exception: 
        return (False, 0) 

    # check that the qks can access vault  
    try: 
        vault_client = VaultClient(config['vault']['host'], config['vault']['port'], config['vault']['token']) 
        if not (await vault_client.connect()) : 
            return (False, -1)
    except Exception: 
        return (False, -1)

    try:  
        redis_client = aioredis.from_url(f"redis://{config['redis']['host']}:{config['redis']['port']}/{config['redis']['db']}", username=config['redis']['user'], password=config['redis']['password'], decode_responses=True)
        if not (await redis_client.ping()) : 
            return (False, -1)
    except Exception: 
        return (False, -1)

    http_client = aiohttp.ClientSession()

    return (True, config['qks']['port'])



    

