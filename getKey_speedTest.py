import asyncio 
import aiohttp
import time 

wsl_ip = "172.23.8.98"

master_SAE_ID = "sae10" 
slave_SAE_ID = "sae20"
slave_SAE_ID_ind = "sae30"
qks1_base = f"http://{wsl_ip}:4001/api/v1/keys/{slave_SAE_ID}/enc_keys" 
qks2_base = f"http://{wsl_ip}:4002/api/v1/keys/{master_SAE_ID}/dec_keys"
qks1_ind = f"http://{wsl_ip}:4001/api/v1/keys/{slave_SAE_ID_ind}/enc_keys" 
qks3_ind = f"http://{wsl_ip}:4003/api/v1/keys/{master_SAE_ID}/dec_keys"


async def test_fun(): 
    http_client = aiohttp.ClientSession()
    start = time.time()
    master_key_list = []
    get_key_data = { "master_SAE_ID" : master_SAE_ID, "size" : 128, "number" : 2}
    async with http_client.post(qks1_base, json=get_key_data) as ret:  
        res = await ret.json() 
        master_key_list = res['keys']
    
    key_ids_list = []
    for key in master_key_list: 
        key_ids_list.append(key['key_ID']) 

    get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID, "key_IDs" : key_ids_list}
    slave_key_list = []
    async with http_client.post(qks2_base, json=get_key_with_ids_data) as ret: 
        res = await ret.json() 
        slave_key_list = res['keys']
    
    for mk, sk in zip(master_key_list, slave_key_list): 
        assert(mk['key'] == sk['key'])
        assert(mk['key_ID'] == sk['key_ID'])

    end = time.time() 
    print(f"DIRECT: successful exchange in {(end-start):.4f} seconds ")


    start = time.time()
    master_key_list = []
    get_key_data = { "master_SAE_ID" : master_SAE_ID, "size" : 128, "number" : 2}
    async with http_client.post(qks1_ind, json=get_key_data) as ret:  
        res = await ret.json() 
        master_key_list = res['keys']
    
    key_ids_list = []
    for key in master_key_list: 
        key_ids_list.append(key['key_ID']) 

    get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID_ind, "key_IDs" : key_ids_list}
    slave_key_list = []
    async with http_client.post(qks3_ind, json=get_key_with_ids_data) as ret:  
        res = await ret.json() 
        slave_key_list = res['keys']
    
    for mk, sk in zip(master_key_list, slave_key_list): 
        assert(mk['key'] == sk['key'])
        assert(mk['key_ID'] == sk['key_ID'])

    end = time.time() 
    print(f"INDIRECT: successful exchange in {(end-start):.4f} seconds ")


    await http_client.close()


asyncio.run(test_fun())



    


    

