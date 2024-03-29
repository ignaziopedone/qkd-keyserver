from aioredis.client import Redis
import yaml
from math import ceil
from uuid import uuid4
from base64 import b64decode, b64encode
from Crypto.Cipher import AES  
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import asyncio

from asyncVaultClient import VaultClient # from VaultClient import VaultClient 
import aiohttp #import requests
from motor.motor_asyncio import AsyncIOMotorClient as MongoClient # from pymongo import MongoClient, ReturnDocument
import aioredis

config : dict = {} 

mongo_client : MongoClient = None # once it has been initialized all APIs use the same client
vault_client : VaultClient = None 
redis_client : Redis = None
http_client : aiohttp.ClientSession = None

# NORTHBOUND 
async def getStatus(slave_SAE_ID : str, master_SAE_ID : str) -> tuple[bool, dict] : 
    global mongo_client, http_client, redis_client, vault_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    master_sae_rt = await redis_client.hgetall(master_SAE_ID) 
    if not master_sae_rt or master_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)

    sae_rt = await redis_client.hgetall(slave_SAE_ID) 
    # if slave_SAE is present in this qkd network
    if not sae_rt : #is not None:  -> check if the returned dict is not empty 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)   

    if sae_rt['dest'] == config['qks']['id']: 
        status = {"message" : f"ERROR: {slave_SAE_ID} registered on this host"}
        return (False, status)

    if sae_rt['cost'] == -1 : 
        status = {"message" : f"ERROR: {slave_SAE_ID} currently unreachable. There are not available paths"}
        return (False, status)
    
    
    res = {
        'source_KME_ID': config['qks']['id'],
        'target_KME_ID': sae_rt['dest'],
        'master_SAE_ID': master_SAE_ID,
        'slave_SAE_ID': slave_SAE_ID,
        'max_key_per_request': int(config['qks']['max_key_per_request']),
        'max_key_size': int(config['qks']['max_key_size']),
        'min_key_size': int(config['qks']['min_key_size']),
        'max_SAE_ID_count': 0
    }

    if sae_rt['dest'] == sae_rt['next'] :
        res['connection_type'] = "direct"
    else: 
        res['connection_type'] = "indirect"

    qkdm_exist = True if res['connection_type'] == "direct" else False 
    key_stream = await key_stream_collection.find_one({"dest_qks.id" : sae_rt['dest'], "qkdm" : {"$exists" : qkdm_exist}})
    
    if key_stream is not None:
        res['key_size'] = key_stream['standard_key_size']
        res['max_key_count'] = key_stream['max_key_count']
        if qkdm_exist: 
            address = key_stream['qkdm']['address']
            
            async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{key_stream['_id']}") as ret: 
                ret_val = await ret.json()
                ret_status = ret_val['status']
                if ret.status == 200 and ret_status == 0: 
                    res['stored_key_count'] = ret_val['available_indexes']
                else: 
                    res['stored_key_count'] = 0
            
        else: 
            res['stored_key_count'] = key_stream['indirect_data']['available_keys']

        return (True, res )
    else: 
        # no stream available but SAE reachable -> hop-by-hop connection 
        res['key_size'] = None
        res['max_key_count'] = None
        res['stored_key_count'] = None
        return (True, res)
 
async def getKey(slave_SAE_ID: str , master_SAE_ID : str, number : int =1, key_size : int = None, extensions = None ) -> tuple[bool, dict] :
    global mongo_client, http_client, redis_client, vault_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    if key_size is None: 
        key_size = config['qks']['def_key_size'] 
    elif key_size > config['qks']['max_key_size'] or key_size < config['qks']['min_key_size'] or key_size % 8 != 0: 
        status = {"message" : "ERROR: please respect key size limits: check them with getStatus function. Size must be a multiple of 8"}
        return (False, status) 

    if number > config['qks']['max_key_per_request'] : 
        status = {"message" : "ERROR: please respect max_key_per_request limit: check it with getStatus function"}
        return (False, status) 


    master_sae_rt = await redis_client.hgetall(master_SAE_ID) 
    if not master_sae_rt or master_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)


    required_direct = False 
    if extensions is not None:
        if len(extensions) == 1 and 'require_direct' in extensions and type(extensions['require_direct'] ) is bool:
            required_direct = extensions['require_direct'] 
        else: 
            status = {"message" : "invalid extensions! The only supported extension is require_direct with boolean value"}
            return (False, status)
         

    slave_sae_rt = await redis_client.hgetall(slave_SAE_ID)

    if not slave_sae_rt or slave_sae_rt["cost"] == -1: 
        status = {"message" : "ERROR: slave_SAE_ID not found on this network or currently unreachable! "}
        return (False, status) 

    qkdm_exists = False 
    if slave_sae_rt['next'] == slave_sae_rt['dest'] : 
        qkdm_exists = True 
        
    if not qkdm_exists and required_direct: # requested only direct, but only indirect are possible 
        status = {"message" : "ERROR: there are not direct connection to this SAE. Try asking for an indirect one ! "}
        return (False, status) 
   
    key_stream = await key_stream_collection.find_one({"dest_qks.id" : slave_sae_rt['dest']}) 

    if key_stream is not None:
        # check available keys and save their ids inside stream.reserved_keys collection 
        needed_keys = number
        list_to_be_sent = []
        used_AKIDs = []

        chunks_for_each_key = int(ceil(float(key_size) / key_stream['standard_key_size'])  ) 
        direct_communication = True 
        address = key_stream['qkdm']['address']
        
        async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{key_stream['_id']}?count=-1") as ret: 
            ret_val = await ret.json()
            ret_status = ret_val['status']
            if ret.status == 200 and ret_status == 0: 
                kids = ret_val['available_indexes'] 
            else:
                status =  {"message" : "ERROR: qkdm unable to answer correctly "} 
                return (False, status )


        # RELAXED APPROACH : IF THERE ARE NOT ENOUGH AVAILABLE KEYS RETURN WHAT IS AVAILABLE
        av_AKIDs = int(len(kids) / chunks_for_each_key)
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

        if len(list_to_be_sent) < 1 : 
            status =  {"message" : "ERROR: unable to reserve any key"} 
            return (False, status )

    else: # multi-hop connection 
        direct_communication = False 
        key_stream = await key_stream_collection.find_one({"_id" : "indirect"}) 
        ## generate key and forward id 

        next_hop = slave_sae_rt['next'] 
        forward_stream = await key_stream_collection.find_one({"dest_qks.id" : next_hop, "qkdm" : {"$exists" : True}}) 
        if forward_stream is None: 
            status = {'message' : f"Multi-hop exchange ERROR: unable to forward, there isn't an available stream to the next hop {next_hop}! "}
            return False, status


        key_chunks = int(ceil(float(AES.key_size[2]*8) / forward_stream['standard_key_size'] )  ) 

        address = forward_stream['qkdm']['address']
        async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{forward_stream['_id']}?count=-1") as ret: 
            ret_val = await ret.json()
            ret_status = ret_val['status']
            if ret.status == 200 and ret_status == 0: 
                kids = ret_val['available_indexes'] 
            else:
                status =  {"message" : "ERROR: qkdm unable to answer correctly "} 
                return (False, status )

        av_AKIDs = int(len(kids) / key_chunks)

        start = 0
        element_to_send = None
        for i in range(0, av_AKIDs): 
            AKID = str(uuid4() )
            AKID_kids = kids[start:(start + key_chunks)]
            start += key_chunks 
            element  = {'AKID' : AKID, 'sae' : f"QKS_{next_hop}", 'kids' : AKID_kids}  
            query =  {"_id" : forward_stream['_id'], "reserved_keys" : {
                "$not" : {
                    "$elemMatch" :  {"kids" : {"$in" : AKID_kids}}
                }        
            }}

            update = {"$push" : {"reserved_keys" : element}}
            res = await key_stream_collection.update_one(query, update)
            if res.modified_count == 1: 
                element_to_send = {'AKID' : AKID, 'kids' : AKID_kids}
                break 

        if element_to_send is None: 
            status =  {"message" : "ERROR: unable to forward due to lack of keys  "} 
            return (False, status )

        post_data = {
            "key_stream_ID" : forward_stream['_id'],
            "slave_SAE_ID" : f"QKS_{next_hop}", 
            "key_size" : AES.key_size[2]*8,
            "key_ID_list" : [element_to_send]
        }

        dest_qks_ip = forward_stream['dest_qks']['address']['ip']
        dest_qks_port = int(forward_stream['dest_qks']['address']['port'])
        async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/keys/QKS_{config['qks']['id']}/reserve", json=post_data) as response:
            if response.status != 200: 
                status = {"message" : "ERROR: peer qks unable to reserve keys", 
                "peer_message" : (await response.json())}
                await key_stream_collection.update_one({"_id" : forward_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : AKID}}})
                return (False, status)

        forwarding_key = await requireSingleKey(forward_stream, element_to_send, AES.key_size[2]*8)
        forward_byte_key = b64decode(forwarding_key['key'])

        list_to_be_sent = []
        keys_to_be_returned = []
        forward_byte_iv = get_random_bytes(AES.key_size[2])
        encypher = AES.new(forward_byte_key, AES.MODE_GCM, forward_byte_iv)
        byte_data_to_forward = int.to_bytes(key_size, 2, byteorder='big')
        for i in range(0, number): 
            retr_key = get_random_bytes(key_size//8)
            retr_key_id = str(uuid4())
            byte_data_to_forward += retr_key_id.encode() + retr_key
            list_to_be_sent.append({'AKID' : retr_key_id})
            keys_to_be_returned.append({'key_ID' : retr_key_id, 'key' : b64encode(retr_key).decode()})
        encrypted_data_to_forward = encypher.encrypt(pad(byte_data_to_forward, AES.block_size)) 

        post_data = {
            'data' : b64encode(encrypted_data_to_forward).decode(),
            'decryption_key_ID' : AKID, 
            'decryption_stream_ID' : forward_stream['_id'], 
            'iv' : b64encode(forward_byte_iv).decode(),
            'destination_sae' : slave_SAE_ID 
        }

        async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/forward", json=post_data) as response:
            if response.status != 200: 
                status = {"message" : "ERROR: error in forward chain", 
                "peer_message" : (await response.json())}
                return (False, status) 

    # send reserveKey(list_to_be_sent) requests to the peer qks
    post_data = {
        "key_stream_ID" : key_stream['_id'],
        "slave_SAE_ID" : slave_SAE_ID, 
        "key_size" : key_size,
        "key_ID_list" : list_to_be_sent
    }

    if key_stream['_id'] == 'indirect' : 
        dest_qks = await qks_collection.find_one({"_id" : slave_sae_rt['dest']})
        dest_qks_ip = dest_qks['address']['ip']
        dest_qks_port = int(dest_qks['address']['port'])
    else: 
        dest_qks_ip = key_stream['dest_qks']['address']['ip']
        dest_qks_port = int(key_stream['dest_qks']['address']['port'])

    async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/keys/{master_SAE_ID}/reserve", json=post_data) as response:
        if response.status != 200: 
            status = {"message" : "ERROR: peer qks unable to reserve keys", 
            "peer_message" : (await response.json())}
            if 'qkdm' in key_stream: 
                await key_stream_collection.update_one({"_id" : key_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : {"$in" : used_AKIDs}}}})
            return (False, status)

    res = {'keys' : [], 'key_container_extension' : {'direct_communication' : direct_communication, 'returned_keys' : len(list_to_be_sent)}}
    if key_stream['_id'] == 'indirect' : 
        res['keys'] = keys_to_be_returned   
    else: 
        tasks = []
        for element in list_to_be_sent: 
            tasks.append(asyncio.create_task(requireSingleKey(key_stream, element, key_size)))  
        res['keys'] = await asyncio.gather(*tasks)
    return (True, res)
        
async def getKeyWithKeyIDs(master_SAE_ID: str, key_IDs:list, slave_SAE_ID:str) -> tuple[bool, dict] :
    global mongo_client, config, http_client, redis_client, vault_client
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    # check that slave_SAE is registered to this qks
    slave_sae_rt = await redis_client.hgetall(slave_SAE_ID) 
    if not slave_sae_rt or slave_sae_rt['dest'] != config['qks']['id']: 
        status = {"message" : "master_SAE_ID not registered on this host"}
        return (False, status)
    
    if len(key_IDs) > config['qks']['max_key_per_request']: 
        status = {"message" : f"ERROR: number of key per request limited to { config['qks']['max_key_per_request']}"}
        return (False, status)   

    # get all streams that have a reserved_key matching one of the requested one
    query = {"reserved_keys" : {"$elemMatch" : {"sae" : master_SAE_ID, "AKID" : {"$in" : key_IDs}}}}
    cursor = stream_collection.find(query)
    matching_streams = await cursor.to_list(length=len(key_IDs)) #mactching streams can't be more than requested keys 

    # if no key available signal it 
    if len(matching_streams) == 0:
        status = {"message" : "none of your requester keys are available!"}
        return (False, status)

    tasks = []
    keys_to_be_returned = { 'keys' : []}
    for key_stream in matching_streams:
        for key in key_stream['reserved_keys']:
            if key['AKID'] in key_IDs and key['sae'] == master_SAE_ID:
                # for each requested AKID require all its chunks and build the aggregate key
                tasks.append(asyncio.create_task(requireSingleKey(key_stream, key, key['key_size'])))
    
    keys_to_be_returned['keys'] = await asyncio.gather(*tasks)
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

    if sae_ID.startswith("QKS_"): 
        value = {"message" : "ERROR: QKS_ prefix in SAE_ID is not allowed "}
        return (False, value)
        

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
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']

    sae_rt = await redis_client.hgetall(sae_ID)
    if not sae_rt or sae_rt['dest'] != config['qks']['id']: 
        value = {"message" : "ERROR: this SAE is NOT registered to this server"}
        return (False, value)
    else : 
        res = await qks_collection.update_one({ "_id": config['qks']['id'] }, { "$pull": { "connected_sae": sae_ID  }})
        await redis_client.publish(f"{config['redis']['topic']}-sae", f"remove-{sae_ID}")
        value = {"message" : "SAE successfully removed from this server"}
        return (True, value) 

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
    await qks_collection.update_one({"_id" : config['qks']['id']}, { "$addToSet": { "neighbor_qks": in_qks["id"]  }})
    await qks_collection.update_one({"_id" : in_qks["id"]}, { "$addToSet": { "neighbor_qks": config['qks']['id']  }})
    await redis_client.publish(f"{config['redis']['topic']}-link", f"add-{dest_qks['_id']}")
    status = {"message" : f"OK: stream {key_stream_ID} started successfully"}
    return (True, status)
        
async def deleteQKDMStreams(qkdm_ID:str) -> tuple[bool, dict] : 
    global mongo_client, config, http_client, redis_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']  
    
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
            "peer_message" : (await response.json())}
            return (False, status)
    
    address = key_stream['qkdm']['address']
    post_data = {'key_stream_ID' : key_stream_ID} 
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/close", json=post_data) as ret: 
        ret_val = await ret.json()
        ret_status = ret_val['status']
        await key_stream_collection.delete_one({"_id" : key_stream_ID})
        await qks_collection.update_one({ "_id": config['qks']['id'] }, { "$pull": { "neighbor_qks": key_stream['dest_qks']['id']  }})
        await qks_collection.update_one({ "_id": key_stream['dest_qks']['id']  }, { "$pull": { "neighbor_qks": config['qks']['id'] }})
        if ret_status == 0 and ret.status == 200:
            status = {"message" : f"OK: stream {key_stream_ID} closed successfully"}
        else: 
            status = {"message" : f"FORCED CLOSURE: stream {key_stream_ID} closed by peer, qkdm is unable to close it but this ID is not valid anymore"}
        await redis_client.publish(f"{config['redis']['topic']}-link", f"remove-{key_stream['dest_qks']['id']}")
        return (True, status)

async def registerQKS(qks_id:str, qks_ip:str, qks_port:int, routing_ip:str, routing_port:int) -> tuple[bool, dict]: 
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
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams'] 
    
    if await key_stream_collection.find_one({"qkdm.id" : qkdm_ID}) is not None: 
        value = {'message' : "ERROR: there are active streams for this QKDM! Please close them before unregister"}
        return (False, value)

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
async def reserveKeys(master_SAE_ID:str, slave_SAE_ID:str, key_stream_ID:str, key_size:int, key_ID_list:list[dict]) -> tuple[bool, dict]: 
    global mongo_client, config, http_client, redis_client, vault_client
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    if (key_size > config['qks']['max_key_size']) or (key_size < config['qks']['min_key_size'] or key_size % 8 != 0) : 
        status = {"message" : "ERROR: requested key size doesn't match this host parameters. Use getStatus to get more information. Size must be a multiple of 8"}
        return (False, status)
 
    slave_sae_rt = await redis_client.hgetall(slave_SAE_ID)
    if not slave_sae_rt and not slave_SAE_ID.startswith("QKS_"): # if slave_SAE_ID starts with "QKS_" this is a forwarding requests between 2 qks 
        status = {"message" : "ERROR: slave_SAE_ID not registered on this host"}
        return (False, status) 

    key_stream = await key_stream_collection.find_one({"_id" : key_stream_ID})
    if key_stream is None: 
        status = {"message" : "ERROR: invalid key_stream_ID"}
        return (False, status) 

    if 'qkdm' in key_stream: # direct
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
            } }}

    else: # indirect 
        akids = [key['AKID'] for key in key_ID_list]
        ret = await vault_client.check(f"{config['qks']['id']}/{key_stream['_id']}", akids)
        if not ret:
            print(f"RESERVE PATH {config['qks']['id']}/{key_stream['_id']}")
            status = {"message" : "ERROR: some kids are not available! "}
            return (False, status)   

        for kid in key_ID_list: 
            kid['sae'] = master_SAE_ID
            kid['key_size'] = key_size 

        query =  {"_id" : key_stream_ID, "reserved_keys" : {
            "$not" : {
                "$elemMatch" :  {"AKID" : {"$in" : list(akids)}}, 
            }} }

 
    update = {"$push" : {"reserved_keys" : {"$each" : key_ID_list}}}
    res = await key_stream_collection.update_one(query, update)
    if res.modified_count != 1:  
        status = {"message" : "ERROR: unable to reserve these keys due to AKID or kids already reserved! "}
        return (False, status)
    else: 
        status = {"message" : "keys reserved correctly!  "}
        return (True, status)


async def forwardData(data:str, decryption_key_id:str, decryption_key_stream_id:str, iv:str, destination_sae:str) -> tuple[bool, dict]:  
    global mongo_client, config, http_client, redis_client 
    key_stream_collection = mongo_client[config['mongo_db']['db']]['key_streams'] 

    sae_rt = await redis_client.hgetall(destination_sae)
    if not sae_rt: # unknown destination sae  -> None or {}
        status = {'message' : "ERROR: UNKNOWN destination SAE"}
        return False, status
        
    next_hop = sae_rt['next'] 
    destination_QKS = sae_rt['dest']
    decoded_data : bytes = b64decode(data) # decode b64 string and get raw bytes   
    decoded_iv : bytes = b64decode(iv) 

    # require key to QKDM 
    dec_stream = await key_stream_collection.find_one({"_id" : decryption_key_stream_id, "reserved_keys.AKID" : decryption_key_id}, {"reserved_keys.$" : 1, "qkdm" : 1})
    if dec_stream is None: 
        status = {'message' : "ERROR: UNKNOWN decryption key stream or key_IDs not properly reserved"}
        return False, status

    address = dec_stream['qkdm']['address']
    post_data = {'key_stream_ID' : decryption_key_stream_id, 'indexes' : dec_stream["reserved_keys"][0]["kids"]}
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_key", json=post_data) as ret: 
        ret_val = await ret.json()
        if ret_val['status'] != 0 or ret.status != 200: 
            status = {'message' : "ERROR: unable to retrieve decryption key"}
            return False, status 
    
    await key_stream_collection.update_one({"_id" : dec_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : decryption_key_id}}})

    chunks = ret_val['keys']
    byte_key = b''
    for el in chunks :
        byte_key += b64decode(el.encode())  

    decypher =  AES.new(byte_key, AES.MODE_GCM, decoded_iv)
    byte_data_to_forward = unpad(decypher.decrypt(decoded_data), AES.block_size) # byte data

    if destination_QKS == config['qks']['id']: 
        size = int.from_bytes(byte_data_to_forward[:2], byteorder='big')
        byte_size = size // 8
        number = (len(byte_data_to_forward)-2) // (36+byte_size)
        res = await key_stream_collection.update_one({"_id" : "indirect",  "available_keys" : { "$lte" : (config['qks']['indirect_max_key_count'] - number) }}, {"$inc" : {"available_keys" : number}})
        if res.modified_count != 1: 
            return False, {'message' : f'ERROR: not enough space available to save the received keys'}
        start = 2
        # save keys into vault 
        while start < len(byte_data_to_forward):
            key_id = byte_data_to_forward[start:start+36].decode()
            key = byte_data_to_forward[start+36:start+36+byte_size]
            key_enc = b64encode(key).decode()
            res = await vault_client.writeOrUpdate(f"{config['qks']['id']}/indirect", str(key_id), {str(key_id) : key_enc}) 
            start += 36 + byte_size
        return True, {'message' : 'key saved successfully'}
    
    else : # -> forward to next hop  
        forward_stream = await key_stream_collection.find_one({"dest_qks.id" : next_hop, "qkdm" : {"$exists" : True}}) 
        if forward_stream is None: 
            status = {'message' : "ERROR: unable to forward, there isn't an available stream to the next hop! "}
            return False, status
        
        key_chunks = int(ceil(float(AES.key_size[2]*8) / forward_stream['standard_key_size'] )  ) 

        address = forward_stream['qkdm']['address']
        async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{forward_stream['_id']}?count=-1") as ret: 
            ret_val = await ret.json()
            ret_status = ret_val['status']
            if ret.status == 200 and ret_status == 0: 
                kids = ret_val['available_indexes'] 
            else:
                status =  {"message" : "ERROR: qkdm unable to answer correctly "} 
                return (False, status )

        av_AKIDs = int(len(kids) / key_chunks)
        
        start = 0
        element_to_send = None
        for i in range(0, av_AKIDs): 
            AKID = str(uuid4() )
            AKID_kids = kids[start:(start + key_chunks)]
            start += key_chunks 
            element  = {'AKID' : AKID, 'sae' : f"QKS_{next_hop}", 'kids' : AKID_kids}  
            query =  {"_id" : forward_stream['_id'], "reserved_keys" : {
                "$not" : {
                    "$elemMatch" :  {"kids" : {"$in" : AKID_kids}}
                }        
            }}

            update = {"$push" : {"reserved_keys" : element}}
            res = await key_stream_collection.update_one(query, update)
            if res.modified_count == 1: 
                element_to_send = [{'AKID' : AKID, 'kids' : AKID_kids}]
                break 

        if element_to_send is None: 
            status =  {"message" : "ERROR: unable to forward due to lack of keys  "} 
            return (False, status )


        post_data = {
            "key_stream_ID" : forward_stream['_id'],
            "slave_SAE_ID" : f"QKS_{next_hop}", 
            "key_size" : AES.key_size[2]*8,
            "key_ID_list" : element_to_send
        }

        dest_qks_ip = forward_stream['dest_qks']['address']['ip']
        dest_qks_port = int(forward_stream['dest_qks']['address']['port'])
        async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/keys/QKS_{config['qks']['id']}/reserve", json=post_data) as response:
            if response.status != 200: 
                status = {"message" : "ERROR: peer qks unable to reserve keys", 
                "peer_message" : (await response.json())}
                await key_stream_collection.update_one({"_id" : forward_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : AKID}}})
                return (False, status)

        qkdm_address = forward_stream['qkdm']['address']
        post_data = {'key_stream_ID' : forward_stream['_id'], 'indexes' : AKID_kids}
        async with http_client.post(f"http://{qkdm_address['ip']}:{qkdm_address['port']}/api/v1/qkdm/actions/get_key", json=post_data) as ret: 
            ret_val = await ret.json()
            ret_status_code = ret.status

        ret_status = ret_val['status']
        if ret_status != 0 or ret_status_code != 200: 
            status = {"message" : "ABORT : THIS SHOULD NOT HAPPEN! there is someone else which is not this QKS that is using the QKDM!"}
            return (False, status)
        chunks : list[str]= ret_val['keys']
        
        forward_byte_key = b''
        for el in chunks :
            forward_byte_key += b64decode(el.encode()) 
        
        await key_stream_collection.update_one({"_id" : forward_stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : AKID}}})
        
        forward_byte_iv = get_random_bytes(AES.key_size[2])
        encypher = AES.new(forward_byte_key, AES.MODE_GCM, forward_byte_iv)
        encrypted_data_to_forward = encypher.encrypt(pad(byte_data_to_forward, AES.block_size)) 

        post_data = {
            'data' : b64encode(encrypted_data_to_forward).decode(),
            'decryption_key_ID' : AKID, 
            'decryption_stream_ID' : forward_stream['_id'], 
            'iv' : b64encode(forward_byte_iv).decode(),
            'destination_sae' : destination_sae 
        }

        async with http_client.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/forward", json=post_data) as response:
            if response.status != 200: 
                status = {"message" : "ERROR: error in forward chain", 
                "peer_message" : (await response.json())}
                return (False, status) 
            else: 
                status = {"message" : "OK: forwarding chain completed"} 
                return (True, status )
     

async def createStream(source_qks_ID:str, key_stream_ID:str, qkdm_id:str) -> tuple[bool, dict]:
    global mongo_client, config, http_client, vault_client
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    qkdm_collection = mongo_client[config['mongo_db']['db']]['qkd_modules']
    
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
                await qks_collection.update_one({"_id" : config['qks']['id']}, { "$addToSet": { "neighbor_qks": dest_qks["id"]  }})
                await qks_collection.update_one({"_id" : dest_qks["id"]}, { "$addToSet": { "neighbor_qks": config['qks']['id']  }})
                await redis_client.publish(f"{config['redis']['topic']}-link", f"add-{source_qks_ID}")
                value = {'message' : "stream successfully created"}
                return (True, value)
            else: 
                value = {'message' : "ERROR in stream creation"}
                return (False, value)

    else: 
        value = {'message' : "ERROR: invalid qkdm_id"}
        return (False, value)

async def closeStream(key_stream_ID:str, source_qks_ID:str) -> tuple[bool, dict]:
    global mongo_client, config, http_client, vault_client
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers']
    
    key_stream =  await stream_collection.find_one({"_id" : key_stream_ID, "dest_qks.id" : source_qks_ID}) 
    if key_stream is None or 'qkdm' not in key_stream:
        value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
        return (False, value)
    

    address = key_stream['qkdm']['address']  
    post_data = {'key_stream_ID' : key_stream_ID} 
    async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/close", json=post_data) as ret:
        ret_val = await ret.json()
        ret_status = ret_val['status']
        if ret_status == 0 and ret.status == 200: 
            await stream_collection.delete_one({"_id" : key_stream_ID})
            await qks_collection.update_one({ "_id": config['qks']['id'] }, { "$pull": { "neighbor_qks": key_stream['dest_qks']['id']  }})
            await qks_collection.update_one({ "_id": key_stream['dest_qks']['id']  }, { "$pull": { "neighbor_qks": config['qks']['id'] }})
            await redis_client.publish(f"{config['redis']['topic']}-link", f"remove-{source_qks_ID}")
            value = {'message' : "direct stream successfully closed"}
            return (True, value)
        else: 
            value = {'message' : "ERROR in stream closure"}
            return (False, value)


# MANAGEMENT FUNCTIONS
async def init_server(config_file_name = "qks_src/config_files/config.yaml") -> tuple[bool, int, dict] : 
    # check that the qks can access admin DB with root credentials  
    global mongo_client, vault_client, config, http_client, redis_client

    config_file = open(config_file_name, 'r')
    config = yaml.safe_load(config_file)
    config_file.close()

    test_mongo_client = MongoClient(f"mongodb://{config['mongo_db']['user']}:{config['mongo_db']['password']}@{config['mongo_db']['host']}:{config['mongo_db']['port']}/admin?authSource={config['mongo_db']['auth_src']}")

    # check that the qks can access mongo
    try: 
        await test_mongo_client.list_database_names()
        mongo_client = MongoClient(f"mongodb://{config['mongo_db']['user']}:{config['mongo_db']['password']}@{config['mongo_db']['host']}:{config['mongo_db']['port']}/{config['mongo_db']['db']}?authSource={config['mongo_db']['auth_src']}")
    
        stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
        indirect_key_stream = {"_id" : "indirect", "reserved_keys" : [] , "available_keys" : 0}
        res  = await stream_collection.update_one({"_id" : "indirect"}, {"$setOnInsert" : indirect_key_stream}, upsert=True)
        
    except Exception as e:  
        print("mongodb exception:", e)
        return (False, -1, {}) 

    # check that the qks can access vault  
    try: 
        vault_client = VaultClient(config['vault']['host'], config['vault']['port'], config['vault']['token']) 
        res = await vault_client.connect() 
        if not res:
            return (False, -1, {})

        await vault_client.createEngine(config['qks']['id'])

    except Exception as e: 
        print("vault exception:", e)
        return (False, -1, {})

    # check that the qks can access redis      
    try:  
        redis_client = aioredis.from_url(f"redis://{config['redis']['host']}:{config['redis']['port']}/{config['redis']['db']}", username=config['redis']['user'], password=config['redis']['password'], decode_responses=True)
        if not (await redis_client.ping()) : 
            return (False, -1, {})
    except Exception as e: 
        print("redis exception:", e)
        

    http_client = aiohttp.ClientSession()

    if 'keycloak' not in config: 
        return (False, -1, {})
    
    return (True, config['qks']['port'], config['keycloak'])


async def requireSingleKey(key_stream: dict, key: dict, size: int) -> dict:
    stream_collection = mongo_client[config['mongo_db']['db']]['key_streams']
    chunks = []
    
    if 'qkdm' in key_stream: 
        address = key_stream['qkdm']['address']
        post_data = {'key_stream_ID' : key_stream["_id"], 'indexes' : key['kids']}
        async with http_client.post(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_key", json=post_data) as ret:
            ret_val = await ret.json()
            ret_status_code = ret.status

        if ret_val['status'] != 0 or ret_status_code != 200:
            return None
        chunks = ret_val['keys']

        byte_key = b''
        for el in chunks :
            byte_key += b64decode(el.encode()) 
        aggregate_key = b64encode(byte_key[0:(size//8)]).decode()

    else: 
        ret = await vault_client.readAndRemove(f"{config['qks']['id']}/{key_stream['_id']}", key['AKID'])
        aggregate_key = ret[key['AKID']] #data in vault are already encoded, indirect keys does not require aggregation


    update_query = {"$pull" : {"reserved_keys" : {"AKID" : key['AKID']}}}
    if 'qkdm' not in key_stream: 
            update_query["$inc"] = {"available_keys" : -1}
    await stream_collection.update_one({"_id" : key_stream['_id']}, update_query)
    
    return {'key_ID' : key['AKID'], 'key' : aggregate_key}