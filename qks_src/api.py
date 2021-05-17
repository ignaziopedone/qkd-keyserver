
import vaultClient
from pymongo import MongoClient
import yaml 

default_key_size = 128

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
def getStatus(slave_SAE_ID : str, master_SAE_ID : str) -> tuple : 
    # TODO : request available keys to qkdms 
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    # check that master_SAE is registered to this qks
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
        key_streams = key_stream_collection.find({"dest_qks" : dest_qks['_id']})
        
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
            return (True, "This sae is connected but is unreachable: no direct connections")
 
    else : 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)   

# TODO
def getKey(slave_SAE_ID: str, master_SAE_ID : str, number : int =1, key_size : int =default_key_size) :
    keys = {'keys' : []}
    return keys

def getKeyWithKeyIDs(master_SAE_ID: str, slave_SAE_ID:str, key_IDs:list) -> tuple :
    # TODO: require single keys (indexes) to qkdms
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']

    # check that master_SAE is registered to this qks
    me = qks_collection.find_one({"_id" : qks['id']})
    my_saes = me['connected_sae']
    if slave_SAE_ID not in my_saes: 
        status = {"message" : "slave_SAE_ID not found in this host"}
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
                    stream_collection.update({"_id" : stream['_id']}, {"$pull" : {"reserved_keys" : {"AKID" : key['AKID']}}})
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
        qks_collection.update({ "_id": qks['id'] }, { "$addToSet": { "connected_sae": sae_ID  }})
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
        qks_collection.update({ "_id": qks['id'] }, { "$pull": { "connected_sae": sae_ID  }})
        value = {"message" : "SAE successfully registered to this server"}
        return (True, value) 

# TODO
def getPreferences() : 
    preferences = {}
    return preferences

# TODO
def setPreference(preference:str, value) : 
    return 

# TODO
def startQKDMStream(qkdm_ID:str) : 
    return 

# TODO
def deleteQKDMStreams(qkdm_ID:str) : 
    return 

# SOUTHBOUND 
# TODO
def registerQKDM(qkdm_ID:str, protocol:str, qkdm_ip:str, destination_qks:str, max_key_count:int, key_size:int): 
    return 

# TODO
def unregisterQKDM(qkdm_ID:str): 
    return 

# EXTERNAL 
# TODO
def reserveKeys(master_SAE_ID:str, slave_SAE_ID:str, key_stream_ID:str, key_lenght:int, key_ID_list:list): 
    # check kids uniqueness in stream.reservedKeys 
    return 

# TODO
def forwardData(data, decryption_key_id:str, decryption_key_stream:str): 
    return 


def createStream(source_qks_ID:str, key_stream_ID:str, stream_type:str, qkdm_address:str=None) -> tuple:
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = mongo_client[mongodb['db']]['quantum_key_servers']
    stream_collection = mongo_client[mongodb['db']]['key_streams']
    qkdm_collection = mongo_client[mongodb['db']]['qkd_modules']
    
    
    if stream_type == "indirect":
        # open an indirect stream 
        return (False, "ERROR: Indirect stream not implemented yet")

    elif stream_type == "direct" and type(qkdm_address) is str:
        if qks_collection.find_one({"_id" : source_qks_ID}) is None or stream_collection.find_one({"_id": key_stream_ID }) is not None:
            value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
            return (False, value)
        
        selected_qkdm = qkdm_collection.find_one({"address.ip" : qkdm_address})
        if  selected_qkdm is not None: 
            # call open connect on the specified qkdm 
            ret_val = 0
            if ret_val == 0: 
                in_qkdm = {"id" : selected_qkdm['_id'], "address" : selected_qkdm['address']}
                new_stream = {"_id" : key_stream_ID, "dest_qks" : source_qks_ID, "reserved_keys" : [], "qkdm" : in_qkdm}
                stream_collection.insert_one(new_stream)
                value = {'message' : "stream successfully created"}
                return (True, value)
            else: 
                value = {'message' : "ERROR in stream creation"}
                return (False, value)

    else: 
        value = {'message' : "ERROR: invalid stream type or qkdm_address"}
        return (False, value)


def closeStream(stream_ID:str, source_qks:str) -> tuple:
    global mongo_client
    if mongo_client is None:
        mongo_client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    stream_collection = mongo_client[mongodb['db']]['key_streams']
    
    stream =  stream_collection.find_one({"_id" : stream_ID, "dest_qks" : source_qks}) 
    if stream is None:
        value = {'message' : "ERROR: invalid qks_ID or stream_ID"}
        return (False, value)
    
    if 'qkdm' in stream : 
        address = stream['qkdm']
        # call close on the specified qkdm 
        ret_val = 0
        if ret_val == 0: 
            stream_collection.delete_one({"_id" : stream_ID})
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
    except: 
        return False 
    


    

