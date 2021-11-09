import asyncio 
import aiohttp
import time

from aiohttp import client 


master_SAE_ID = "sae1" 
slave_SAE_ID = "sae2"
slave_SAE_ID_ind = "sae3"
qks1_base = f"http://localhost:4001/api/v1/keys/{slave_SAE_ID}/enc_keys" 
qks2_base = f"http://localhost:4002/api/v1/keys/{master_SAE_ID}/dec_keys"
qks1_ind = f"http://localhost:4001/api/v1/keys/{slave_SAE_ID_ind}/enc_keys" 
qks3_ind = f"http://localhost:4003/api/v1/keys/{master_SAE_ID}/dec_keys"
keycloak_url = f"http://keycloak:8080/auth/realms/qks/protocol/openid-connect/token"

client_secret = "29db8d09-97f1-4e5c-8744-9e07bd4ff65a"
password = "password"

auth_master = {'Autorization' : ''}
auth_slave = {'Autorization' : ''}
auth_slave_ind = {'Autorization' : ''}

async def auth_fun(): 
    global auth_master, auth_slave, auth_slave_ind 
    http_client = aiohttp.ClientSession()

    auth_string_master = f"client_id=qkstest&client_secret={client_secret}&grant_type=password&scope=openid&username={master_SAE_ID}&password={password}"
    auth_string_slave = f"client_id=qkstest&client_secret={client_secret}&grant_type=password&scope=openid&username={slave_SAE_ID}&password={password}"
    auth_string_slave_ind = f"client_id=qkstest&client_secret={client_secret}&grant_type=password&scope=openid&username={slave_SAE_ID_ind}&password={password}"
    auth_headers = {'Content-Type':'application/x-www-form-urlencoded'}

    try: 
        async with http_client.post(keycloak_url, data=auth_string_master, headers=auth_headers, timeout = 1) as auth_res:  
            ret_json = await auth_res.json()
            auth_master = {'Autorization' : f"Bearer {ret_json['access_token']}"}

        async with http_client.post(keycloak_url, data=auth_string_slave, headers=auth_headers, timeout = 1) as auth_res:  
            ret_json = await auth_res.json()
            auth_slave = {'Autorization' : f"Bearer {ret_json['access_token']}"}
        
        async with http_client.post(keycloak_url, data=auth_string_slave_ind, headers=auth_headers, timeout = 1) as auth_res:  
            ret_json = await auth_res.json()
            auth_slave_ind = {'Autorization' : f"Bearer {ret_json['access_token']}"}

        print("AUTH DONE")
        return None 

    except Exception as e: 
        return e 

    finally: 
        await http_client.close()



async def test_fun(t:str, number:int, size:int): 
    
    http_client = aiohttp.ClientSession()
    start = time.time()
    master_key_list = []
    get_key_data = { "master_SAE_ID" : master_SAE_ID, "size" : size, "number" : number}
    print("TEST FUN STARTED")
    
    try: 
        res = None
        if t == "direct":
            async with http_client.post(qks1_base, json=get_key_data, headers=auth_master, timeout = 1) as ret:  
                res = await ret.json() 
                master_key_list = res['keys']
        else:
            async with http_client.post(qks1_ind, json=get_key_data, headers=auth_master, timeout = 1) as ret:  
                res = await ret.json() 
                master_key_list = res['keys']
        
        key_ids_list = []
        for key in master_key_list: 
            key_ids_list.append(key['key_ID']) 
        
        slave_key_list = []
        if t == "direct": 
            get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID, "key_IDs" : key_ids_list}
            async with http_client.post(qks2_base, json=get_key_with_ids_data, headers=auth_slave, timeout = 1) as ret: 
                res = await ret.json() 
                slave_key_list = res['keys']
        else: 
            get_key_with_ids_data = {"slave_SAE_ID" : slave_SAE_ID_ind, "key_IDs" : key_ids_list}
            async with http_client.post(qks3_ind, json=get_key_with_ids_data, headers=auth_slave_ind, timeout = 1) as ret: 
                res = await ret.json() 
                slave_key_list = res['keys']
        
        for mk, sk in zip(master_key_list, slave_key_list): 
            assert(mk['key'] == sk['key'])
            assert(mk['key_ID'] == sk['key_ID'])

        end = time.time()  
        print(f"    {t}  {number} keys {size} bit:  in {(end-start):.3f} sec")

        
    except Exception as e:
        print(e, res)
        
    finally: 
        await http_client.close()

async def main():
    tasks = [] 

    res = await auth_fun()
    if res is not None: 
        print(f"ERROR: {res}")
        return 

    #start = time.time() 
    #tasks.append(asyncio.create_task(test_fun("direct", 1, 128)))
    #tasks.append(asyncio.create_task(test_fun("direct", 10, 128)))
    #tasks.append(asyncio.create_task(test_fun("direct", 1, 512)))
    #tasks.append(asyncio.create_task(test_fun("indirect", 2, 256))) 
    #res = await asyncio.gather(*tasks)
    #end = time.time() 
    print(f"PARALLEL = {(end-start):.3f} sec \n")

    #await asyncio.sleep(0.5)

    #start2 = time.time()
    #await test_fun("direct", 1, 128)
    #await test_fun("direct", 10, 128)
    #await test_fun("direct", 1, 512)
    #await test_fun("indirect", 2, 256)

    #end2 = time.time()
    #print(f"SEQUENTIAL = {(end2-start2):.3f} sec \n")

asyncio.run(main())




    


    

