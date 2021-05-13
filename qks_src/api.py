import vaultClient

default_key_size = 128

# NORTHBOUND 
def getStatus(slave_SAE_ID, master_SAE_ID) : 
    res = {}
    return res 

def getKey(slave_SAE_ID, master_SAE_ID, number=1, key_size=default_key_size) :
    keys = {'keys' : []}
    return keys

def getKeyWithKeyIDs(master_SAE_ID, slave_SAE_ID, key_IDs) :
    keys = {'keys' : []}
    return keys

def getQKDMs() : 
    qkdms = {'QKDM_list' : []}
    return qkdms

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


