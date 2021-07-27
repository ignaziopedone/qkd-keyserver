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


async def test_fun(t:str, number:int, size:int): 
    
    http_client = aiohttp.ClientSession()
    start = time.time()
    master_key_list = []
    get_key_data = { "master_SAE_ID" : master_SAE_ID, "size" : size, "number" : number}
    
    if t == "direct":
        async with http_client.post(qks1_base, json=get_key_data) as ret:  
            res = await ret.json() 
            master_key_list = res['keys']
    else:
        async with http_client.post(qks1_ind, json=get_key_data) as ret:  
            res = await ret.json() 
            master_key_list = res['keys']
    
    key_ids_list = []
    for key in master_key_list: 
        key_ids_list.append(key['key_ID']) 

    
    slave_key_list = []
    if t == "direct": 
        get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID, "key_IDs" : key_ids_list}
        async with http_client.post(qks2_base, json=get_key_with_ids_data) as ret: 
            res = await ret.json() 
            slave_key_list = res['keys']
    else: 
        get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID_ind, "key_IDs" : key_ids_list}
        async with http_client.post(qks3_ind, json=get_key_with_ids_data) as ret: 
            res = await ret.json() 
            slave_key_list = res['keys']
    
    for mk, sk in zip(master_key_list, slave_key_list): 
        assert(mk['key'] == sk['key'])
        assert(mk['key_ID'] == sk['key_ID'])

    end = time.time() 
    if t == "direct": 
        print(f"    DIRECT  {number} keys {size} bit:  in {(end-start):.3f} sec")
    else: 
        print(f"    INDIRECT  {number} keys {size} bit: in {(end-start):.3f} sec")

    await http_client.close()

async def main():
    tasks = [] 
    start = time.time() 
    tasks.append(asyncio.create_task(test_fun("direct", 2, 128)))
    tasks.append(asyncio.create_task(test_fun("direct", 6, 256)))
    tasks.append(asyncio.create_task(test_fun("indirect", 2, 128)))
    tasks.append(asyncio.create_task(test_fun("indirect", 6, 256))) 
    res = await asyncio.gather(*tasks)
    end = time.time() 
    print(f"PARALLEL = {(end-start):.3f} sec \n")

    await asyncio.sleep(0.5)

    start2 = time.time()
    await test_fun("direct", 2, 128)
    await test_fun("direct", 6, 256)
    await test_fun("indirect", 2, 128)
    await test_fun("indirect", 6, 256)
    end2 = time.time()
    print(f"SEQUENTIAL = {(end2-start2):.3f} sec \n")

asyncio.run(main())




    


    

