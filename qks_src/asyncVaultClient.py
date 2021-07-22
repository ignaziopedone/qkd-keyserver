import async_hvac as hvac 

class VaultClient() : 
    def __init__(self, address:str, port:int, token:str = None, tls:bool = False, keys:list = []): 
        if tls: 
            self.client = hvac.AsyncClient(url='https://'+address+":"+str(port), verify=False)
        else: 
            self.client = hvac.AsyncClient(url='http://'+address+":"+str(port))
        self.client.token = token
        self.keys = keys
        

    async def initialize(self, shares:int, threshold:int) -> bool: 
        if not (await self.client.is_initialized()):
            result = await self.client.initialize(shares, threshold)
            self.client.token = result['root_token']
            self.keys = result['keys_base64']  
            return await self.client.is_initialized() 
        return True

    async def unseal(self, keys:list = None) -> bool: 
        if not keys: 
            keys = self.keys
        if (await self.client.is_sealed()) and keys :
            await self.client.unseal_multi(keys)
        return not (await self.client.is_sealed()) 
    
    async def seal(self) -> bool: 
        if not (await self.client.is_sealed()) :
            await self.client.seal()
        return await self.client.is_sealed() 
            
    async def connect(self, token:str = None) -> bool: 
        if token is not None: 
            self.client.token = token
        
        x = await self.client.is_initialized()
        if not (x): 
            return False

        return await self.client.is_authenticated()

    async def approle_login(self, role_id:str, secret_id:str) -> bool: 
        try: 
            r = await self.client.auth_approle(role_id, secret_id) 
            return True
        except Exception as e: 
            return False

    async def createEngine(self, mount:str) -> bool: 
        # path = qkdm_id
        try:
            await self.client.enable_secret_backend(backend_type='kv', mount_point=mount, options={'version':1})
            return True
        except Exception: 
            return False 

    async def disableEngine(self, mount:str) -> bool  :
        # path = qkdm_id 
        try:
            response = await self.client.disable_secret_backend(mount_point=mount)
            return True
        except Exception: 
            return False 

    async def writeOrUpdate(self, mount:str, path:str, data:dict) -> bool: 
        # mount = qkdm_id + key_stream_ID   # path = key_id
        try: 
            answer = await self.client.write(mount + "/" + path, **data)
            return True
        except Exception as e : 
            return False

        
    async def readAndRemove(self, mount:str, path:str) -> dict: 
        # mount = qkdm_id + key_stream_ID   # path = key_id
        try: 
            data = await self.client.read(path=mount + "/" + path)
            ret = data['data']
 
            await self.client.delete(path = mount + "/" + path)
            return ret

        except Exception: 
            return None 

    async def remove(self, mount:str, path:str) -> bool: 
        # mount = qkdm_id + key_stream_ID   # path = key_id
        try:  
            await self.client.delete(path = mount + "/" + path)
            return True
        except Exception: 
            return False 

    async def read(self, mount:str, path:str) -> dict: 
        # mount = qkdm_id + key_stream_ID   # path = key_id
        try: 
            data = await self.client.read(path=mount + "/" + path)
            ret = data['data']
            return ret

        except Exception: 
            return None 

    async def check(self, mount:str, paths:list) -> bool:
        # mount = qkdm_id + key_stream_ID   # paths = key_ids list
        try: 
            data = await self.client.list(path = mount )
            for path in paths: 
                if path not in data['data']['keys']: 
                    return False 
            return True 

        except Exception: 
            return False 
    
    async def list(self, mount:str) -> list: 
        # mount = qkdm_id + key_stream_ID
        try: 
            data = await self.client.list(path = mount)
            return data['data']['keys']

        except Exception: 
            return False 

    async def createUser(self, id:str) -> dict: 
        res = await self.client.list_auth_backends()
        auth_methods = res['data'].keys()
        if 'approle/' not in auth_methods: 
            await self.client.enable_auth_backend('approle')

        res = await self.createEngine(id)

        policy = """
            path "%s/*" {
            capabilities = ["create", "read", "update", "delete", "list"]
            }""" % id
        
        if res : 

            await self.client.set_policy(name=id, rules=policy)
            await self.client.create_role(role_name=id, token_policies=[id], token_type='service', mount_point="approle")

            response = {}
            response["role_id"] = await self.client.get_role_id(role_name=id)
            r = await self.client.create_role_secret_id(role_name=id)
            response["secret_id"] = r['data']['secret_id']
            return response

        else : 
            return None

    async def deleteUser(self, id:str) -> bool: 
        try: 
            await self.client.delete_role(id)
            res = await self.disableEngine(id)
            return res 
        except Exception : 
            return False

    async def close(self) -> bool : 
        await self.client.close()
