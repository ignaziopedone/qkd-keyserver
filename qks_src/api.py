import vaultClient
from pymongo import MongoClient
import yaml 

default_key_size = 128

config_file = open("qks_src/config.yaml", 'r')
prefs = yaml.safe_load(config_file)

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
def getStatus(slave_SAE_ID, master_SAE_ID) : 
    # TODO : request available keys to qkdms 
    client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qks_collection = client[mongodb['db']]['quantum_key_servers']

    me = qks_collection.find_one({"_id" : qks['id']})
    my_saes = me['connected_sae']
    if master_SAE_ID not in my_saes: 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)
    
    dest_qks = qks_collection.find_one({ "connected_sae": slave_SAE_ID }) 

    if dest_qks is not None: 
        res = {
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
        key_stream_collection = client[mongodb['db']]['key_streams']
        key_streams = key_stream_collection.find({"dest_qks" : dest_qks['_id']})
        for stream in key_streams: 
            module = stream['qkdm']
            # available keys to module
            av_k = 0
            stored_key_count += av_k
        
        res['stored_key_count'] = stored_key_count
        return (True, res )
 
    else : 
        status = {"message" : "slave_SAE_ID not found in this qkd network"}
        return (False, status)   


def getKey(slave_SAE_ID, master_SAE_ID, number=1, key_size=default_key_size) :
    keys = {'keys' : []}
    return keys

def getKeyWithKeyIDs(master_SAE_ID, slave_SAE_ID, key_IDs) :
    keys = {'keys' : []}
    return keys

def getQKDMs() : 
    client = MongoClient(f"mongodb://{mongodb['user']}:{mongodb['password']}@{mongodb['host']}:{mongodb['port']}/{mongodb['db']}?authSource={mongodb['auth_src']}")
    qkdm_collection = client[mongodb['db']]['qkd_modules']
    qkdm_list = qkdm_collection.find()
    mod_list = []
    for qkdm in qkdm_list:  
        mod_list.append(qkdm)
    qkdms = {'QKDM_list' : mod_list}
    return (True, qkdms)

def registerSAE(sae_ID) : 
    # push to redis 
    return 

def unregisterSAE(sae_ID) : 
    # push to redis 
    return 

def getPreferences() : 
    preferences = {}
    return preferences

def setPreference(preference, value) : 
    return 

def startQKDMStream(qkdm_ID) : 
    return 

def deleteQKDMStreams(qkdm_ID) : 
    return 

# SOUTHBOUND 
def registerQKDM(qkdm_ID, protocol, qkdm_ip, destination_qks, max_key_count, key_size): 
    return 

def unregisterQKDM(qkdm_ID): 
    return 

# EXTERNAL 
def reserveKeys(master_SAE_ID, slave_SAE_ID, key_stream_ID, key_lenght, key_ID_list): 
    return 

def forwardData(data, decryption_key_id, decryption_key_stream): 
    return 

def createStream(source_qks_ID, key_stream_ID, stream_type, qkdm_address=None):
    return

def closeStream(stream_ID, source_qks):
    return 


# managment functions 
def check_mongo_init() : 
    user = mongodb['user']
    password = mongodb['password']
    auth_src = mongodb['auth_src']
    host = mongodb['host']
    port = mongodb['port']
    client = MongoClient(f"mongodb://{user}:{password}@{host}:{port}/admin?authSource={auth_src}")

    try: 
        client.list_database_names() 
        return True
    except: 
        return False 
    


    

