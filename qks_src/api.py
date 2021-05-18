
import vaultClient
from pymongo import MongoClient
import yaml
import requests 

config_file = open("qks_src/config.yaml", 'r')
prefs = yaml.safe_load(config_file)
mongo_client = None # once it has been initialized all APIs use the same client

mongodb = {
    'host' : prefs['mongo_db']['host'],
    'port' : prefs['mongo_db']['port'], 
    'user' : prefs['mongo_db']['user'],
    'password' : prefs['mongo_db']['password'],
    'auth_src' : prefs['mongo_db']['auth_src'],
    'db' : prefs['mongo_db']['db_name']
}

qks = {
    'id' : prefs['qks']['KME_ID'],
    'def_key_size' : prefs['qks']['DEF_KEY_SIZE'],
    'max_key_count' : prefs['qks']['MAX_KEY_COUNT'],
    'max_key_per_request' : prefs['qks']['MAX_KEY_PER_REQUEST'],
    'max_key_size' : prefs['qks']['MAX_KEY_SIZE'],
    'min_key_size' : prefs['qks']['MIN_KEY_SIZE'],
    'max_sae_id_count' : prefs['qks']['MAX_SAE_ID_COUNT']
}


# NORTHBOUND 
def getStatus(slave_SAE_ID : str, master_SAE_ID : str = None) -> tuple : 
    # TODO : request available keys to qkdms 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    # check that master_SAE is registered to this qks
    if master_SAE_ID is not None:
        me = qks_collection.find_one({"_id" : qks['id']})
        my_saes = me['connected_sae']
        if master_SAE_ID not in my_saes: 
            status = {"message" : "master_SAE_ID not registered on this host"}
            return (False, status)
    
    dest_qks = qks_collection.find_one({ "connected_sae": slave_SAE_ID }) 
    # if slave_SAE is present in this qkd network
    if dest_qks is not None: 
        res = {
            # where there are values that can be different between master and slave host choose the more conservative one
            'source_KME_ID': qks['id'],
            'target_KME_ID': dest_qks['_id'],
            'master_SAE_ID': master_SAE_ID,
            'slave_SAE_ID': slave_SAE_ID,
            'key_size': int(dest_qks['qos']['DEF_KEY_SIZE']),
            'max_key_count': int(dest_qks['qos']['MAX_KEY_COUNT']),
            'max_key_per_request': int(min(dest_qks['qos']['MAX_KEY_PER_REQUEST'], qks['max_key_per_request'])),
            'max_key_size': int(min(dest_qks['qos']['MAX_KEY_SIZE'], qks['max_key_size'])),
            'min_key_size': int(max(dest_qks['qos']['MIN_KEY_SIZE'], qks['max_key_size'])),
            'max_SAE_ID_count': int(min(dest_qks['MAX_SAE_ID_COUNT'], qks['max_sae_id_count']) if 'MAX_SAE_ID_COUNT' in dest_qks else 0)
        }
        stored_key_count = 0 
        key_stream_collection = mongo_client[mongodb['db']]['key_streams']
        key_streams = key_stream_collection.find({"dest_qks.id" : dest_qks['_id']})
        
        if key_streams.count() !=0:
            for stream in key_streams: 
                module = stream['qkdm']
                # ask available keys to module
                av_k = 0
                stored_key_count += av_k
            
            res['stored_key_count'] = stored_key_count
            return (True, res )
        else: 
            # no stream available. Try to open an indirect connection
            status = {"message" : "ERROR: This sae is connected but is unreachable: no direct connections are available"}
            return (True, status)
 
    else : 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)   

# TODO
def getKey(slave_SAE_ID: str , master_SAE_ID : str = None, number : int =1, key_size : int = None) :
    if key_size is None: 
        key_size = qks['def_key_size']
    keys = {'keys' : []}
    return keys

def getKeyWithKeyIDs(master_SAE_ID: str, key_IDs:list, slave_SAE_ID:str = None) -> tuple :
    # TODO: require single keys (indexes) to qkdms
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    # check that slave_SAE is registered to this qks
    if slave_SAE_ID is not None:
        me = qks_collection.find_one({"_id" : qks['id']})
        my_saes = me['connected_sae']
        if slave_SAE_ID not in my_saes: 
            status = {"message" : "ERROR: slave_SAE_ID not found in this host"}
            return (False, status)
    
    if len(key_IDs) > qks['max_key_per_request']: 
        status = {"message" : f"ERROR: number of key per request limited to { qks['max_key_per_request']}"}
        return (False, status)   

    # get all streams that have a reserved_key matching one of the requested one
    stream_collection = mongo_client[mongodb['db']]['key_streams']
    query = {"reserved_keys" : {"$elemMatch" : {"sae" : master_SAE_ID, "AKID" : {"$in" : key_IDs}}}}
    matching_streams = stream_collection.find(query)

    # if no key available signal it 
    if matching_streams.count() == 0:
        status = {"message" : "none of your requester keys are available!"}
        return (False, status)

    keys_to_be_returned = { 'keys' : []}
    for stream in matching_streams:
        for key in stream['reserved_keys']:
            if key['AKID'] in key_IDs and key['sae'] == master_SAE_ID:
                # for each requested AKID require all its chunks and build the aggregate key
                # TODO: require key['kids'] to modules 
                ret_status, returned_keys = (True, {"ind1" : "chunk1", "ind2" : "chunk2"})
                if ret_status: 
                    # if a key is not available in the module it won't be returned but the other keys will be returned correctly
                    aggregate_key = ""
                    for val in returned_keys.values():
                        aggregate_key += val
                    keys_to_be_returned['keys'].append({'key_ID' : key['AKID'], 'key' : aggregate_key})

                    # remove akid from reserved keys
                    stream_collection.update_one({"_id" : stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : key['AKID']}}})
    return (True, keys_to_be_returned)

def getQKDMs() -> tuple: 
    # return the whole qkdm collection
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qkdms_collection = mongo_client[mongodb['db']]['qkd_modules']
    qkdm_list = qkdms_collection.find()
    mod_list = []
    for qkdm in qkdm_list:  
        mod_list.append(qkdm)
    qkdms = {'QKDM_list' : mod_list}
    return (True, qkdms)

def registerSAE(sae_ID: str) -> tuple: 
    # TODO: push to redis 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    sae_qks = qks_collection.find_one({"connected_sae" : sae_ID})
    if sae_qks is not None: 
        value = {"message" : "ERROR: this SAE is already registered in this network"}
        return (False, value)
    else : 
        res = qks_collection.update_one({ "_id": qks['id'] }, { "$addToSet": { "connected_sae": sae_ID  }})
        value = {"message" : "SAE successfully registered to this server"}
        return (True, value)

def unregisterSAE(sae_ID: str) -> tuple: 
    # TODO: push to redis 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    sae_qks = qks_collection.find_one({"_id" : qks['id'], "connected_sae" : sae_ID})
    if sae_qks is None: 
        value = {"message" : "ERROR: this SAE is NOT registered to this server"}
        return (False, value)
    else : 
        res = qks_collection.update_one({ "_id": qks['id'] }, { "$pull": { "connected_sae": sae_ID  }})
        value = {"message" : "SAE successfully registered to this server"}
        return (True, value) 

# TODO
def getPreferences() : 
    preferences = {}
    return preferences

# TODO
def setPreference(preference:str, value) : 
    return 

def startQKDMStream(qkdm_ID:str) : 
    # TODO: interaction with QKDM and REDIS
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']  
    qkdm_collection = mongo_client[mongodb['db']]['qkd_modules']  
    key_stream_collection = mongo_client[mongodb['db']]['key_streams'] 
    

    qkdm = qkdm_collection.find_one({"_id" : qkdm_ID})
    if qkdm is None: 
        status = {"message" : "ERROR: this qkdm is not registered on this host! "}
        return (False, status)

    qkdm_stream = key_stream_collection.find_one({"qkdm.id" : qkdm_ID})
    if qkdm_stream is not None: 
        status = {"message" : "ERROR: there is already an active stream for this qkdm. This QKS version only allows 1 stream per qkdm "}
        return (False, status)
    
    qkdm_address = qkdm['address']['ip']
    qkdm_port = qkdm['address']['port']
    # call OPEN_CONNECT on the found QKDM 
    res, key_stream_ID = 0, "stream3" 
    if res != 0: 
        status = {"message" : "ERROR: QKDM unable to open the stream"}
        return (False, status)
        
    post_data = {
        'qkdm_id' : qkdm['reachable_qkdm'],
        'source_qks_ID' : qks['id'],
        'type' : "direct",
        'key_stream_ID' : key_stream_ID
    }

    # call createStream on the peer qks 
    dest_qks = qks_collection.find_one({"_id" : qkdm['reachable_qks']})
    dest_qks_ip = dest_qks['address']['ip']
    dest_qks_port = int(dest_qks['address']['port'])
    response = requests.post(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/streams", json=post_data)
     
    if response.status_code != 200 :
        status = {"message" : "ERROR: peer QKS unable to create the stream"}
        return (False, status)
    
    # everything ok: insert the stream in the db 
    in_qkdm = {"id" : qkdm['_id'], "address" : qkdm['address']}
    in_qks = {"id" :  dest_qks['_id'], "address" : dest_qks['address']}
    stream = {"_id" : key_stream_ID+"a", 
        "dest_qks" : in_qks, 
        "standard_key_size" : qkdm['parameters']['standard_key_size'], 
        "reserved_keys" : [], 
        "qkdm" : in_qkdm
    }
    key_stream_collection.insert_one(stream)
    # PUSH TO REDIS 
    status = {"message" : f"OK: stream {key_stream_ID} started successfully"}
    return (True, status)
        
def deleteQKDMStreams(qkdm_ID:str) : 
    # TODO: interaction with QKDM and REDIS 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    key_stream_collection = mongo_client[mongodb['db']]['key_streams'] 
    
    stream = key_stream_collection.find_one({"qkdm.id" : qkdm_ID})
    if stream is None: 
        status = {"message" : "There are no active stream for this QKDM on this host "}
        return (False, status)
    key_stream_ID = stream["_id"]
    key_stream_ID_s = key_stream_ID[:-1]
        
    delete_data = {
        'source_qks_ID' : qks['id'],
        'key_stream_ID' : key_stream_ID
    }

    # call closeStream on the peer qks 
    dest_qks_ip = stream['dest_qks']['address']['ip']
    dest_qks_port = int(stream['dest_qks']['address']['port'])
    response = requests.delete(f"http://{dest_qks_ip}:{dest_qks_port}/api/v1/streams/{key_stream_ID_s}", json=delete_data)
     
    if response.status_code != 200 :
        status = {"message" : "ERROR: peer QKS unable to close the stream", 
        "peer_message" : response.text}
        return (False, status)
    
    qkdm_address = stream['qkdm']['address']['ip']
    qkdm_port = stream['qkdm']['address']['port']
    # call CLOSE on the found QKDM 
    res = 0

    key_stream_collection.delete_one({"_id" : key_stream_ID})
    # push to REDIS 
    if res == 0:
        status = {"message" : f"OK: stream {key_stream_ID} closed successfully"}
    else: 
        status = {"message" : f"FORCED CLOSURE: stream {key_stream_ID} closed by peer, qkdm is unable to close it but this ID is not valid anymore"}
    return (True, status)


# SOUTHBOUND 
# TODO
def registerQKDM(qkdm_ID:str, protocol:str, qkdm_ip:str, destination_qks:str, max_key_count:int, key_size:int): 
    return 

# TODO
def unregisterQKDM(qkdm_ID:str): 
    return 

# EXTERNAL 
def reserveKeys(master_SAE_ID:str, slave_SAE_ID:str, key_stream_ID:str, key_lenght:int, key_ID_list:list): 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']  
    key_stream_collection = mongo_client[mongodb['db']]['key_streams']

    if (key_lenght > qks['max_key_size']) or (key_lenght < qks['min_key_size']) : 
        status = {"message" : "ERROR: requested key size doesn't match this host parameters. Use getStatus to get more information"}
        return (False, status)

    me = qks_collection.find_one({"_id" : qks['id'], "connected_sae" : slave_SAE_ID})
    if me is None: 
        status = {"message" : "ERROR: slave_SAE_ID not registered on this host"}
        return (False, status) 

    key_stream = key_stream_collection.find_one({"_id" : key_stream_ID})
    if key_stream is None: 
        status = {"message" : "ERROR: invalid key_stream_ID"}
        return (False, status) 

    valid_list = True
    kids_to_be_checked = set()
    akids = set()
    for element in key_ID_list: 
        if not('AKID' in element and 'kids' in element and type(element['kids']) is list) or (key_stream['standard_key_size']*len(element['kids']) != key_lenght): 
            valid_list = False
            break
        else: 
            element['sae'] : master_SAE_ID
            kids_to_be_checked.update(element['kids'])
            akids.add(element['AKID'])

    if not valid_list: 
        status = {"message" : "ERROR: key_ID_list not properly formatted"}
        return (False, status)
    
    kids_per_akid = int(key_lenght / key_stream['standard_key_size'])
    if (len(akids) != len(key_ID_list)) or len(kids_to_be_checked)!= len(akids)*kids_per_akid : 
        status = {"message" : "ERROR: there are some duplication in AKIDs or kids received"}
        return (False, status) 

    if 'qkdm' not in key_stream: 
        status = {"message" : "ERROR: indirect streams not supported yet"}
        return (False, status) 

    
    # TODO: check valid kids with the module 
    res = 0
    available_kids = True if res == 0 else False
    if not available_kids:
        status = {"message" : "ERROR: some kids are not available! "}
        return (False, status)  

    query =  {"_id" : key_stream_ID, "reserved_keys" : {
        "$not" : {
            "$elemMatch" :  {"$or" : [
                {"AKID" : {"$in" : akids}}, 
                {"kids" : {"$in" : kids_to_be_checked}}]
            }
        } 
    }}
 
    update = {"$push" : {"reserved_keys" : {"$each" : key_ID_list}}}
    res = key_stream_collection.update_one(query, update)
    print(f"find: {res.matched_count} - updated : {res.modified_count}")
    if res.modified_count != 1:  
        status = {"message" : "ERROR: unable to reserve these keys due to AKID or kids duplication! "}
        return (False, status)
    else: 
        status = {"message" : "keys reserved correctly!  "}
        return (True, status)


# TODO
def forwardData(data, decryption_key_id:str, decryption_key_stream:str): 
    return 


def createStream(source_qks_ID:str, key_stream_ID:str, stream_type:str, qkdm_id:str=None) -> tuple:
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']
    stream_collection = mongo_client[mongodb['db']]['key_streams']
    qkdm_collection = mongo_client[mongodb['db']]['qkd_modules']
    
    
    if stream_type == "indirect":
        # open an indirect stream 
        return (False, "ERROR: Indirect stream not implemented yet")

    elif stream_type == "direct" and type(qkdm_id) is str:
        source_qks = qks_collection.find_one({"_id" : source_qks_ID})
        if  source_qks is None or stream_collection.find_one({"_id": key_stream_ID }) is not None:
            value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
            return (False, value)
        
        selected_qkdm = qkdm_collection.find_one({"_id" : qkdm_id})
        if  selected_qkdm is not None: 
            # call open connect on the specified qkdm 
            ret_val = 0
            if ret_val == 0: 
                in_qkdm = {"id" : selected_qkdm['_id'], "address" : selected_qkdm['address']}
                dest_qks = {"id" : source_qks_ID, "address" : source_qks['address']}
                new_stream = {"_id" : key_stream_ID, "dest_qks" : dest_qks, "reserved_keys" : [], "qkdm" : in_qkdm, "standard_key_size" : selected_qkdm['parameters']['standard_key_size']}
                stream_collection.insert_one(new_stream)
                value = {'message' : "stream successfully created"}
                return (True, value)
            else: 
                value = {'message' : "ERROR in stream creation"}
                return (False, value)

    else: 
        value = {'message' : "ERROR: invalid stream type or qkdm_id"}
        return (False, value)


def closeStream(key_stream_ID:str, source_qks_ID:str) -> tuple:
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    stream_collection = mongo_client[mongodb['db']]['key_streams']
    
    stream =  stream_collection.find_one({"_id" : key_stream_ID, "dest_qks.id" : source_qks_ID}) 
    if stream is None:
        value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
        return (False, value)
    
    if 'qkdm' in stream : 
        address = stream['qkdm']
        # call close on the specified qkdm 
        ret_val = 0
        if ret_val == 0: 
            stream_collection.delete_one({"_id" : key_stream_ID})
            value = {'message' : "stream successfully closed"}
            return (True, value)
        else: 
            value = {'message' : "ERROR in stream closure"}
            return (False, value)
    else: 
        # close indired stream
        return (False, "not implemented yet") 


# MANAGEMENT FUNCTIONS

def check_mongo_init() -> bool:
    # check that the qks can access admin DB with root credentials  
    user = mongodb['user']
    password = mongodb['password']
    auth_src = mongodb['auth_src']
    host = mongodb['host']
    port = mongodb['port']
    test_mongo_client = MongoClient(f"mongodb://{user}:{password}@{host}:{port}/admin?authSource={auth_src}")

    try: 
        test_mongo_client.list_database_names() 
        return True
    except Exception: 
        return False 
    


    

