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
            self.keys = result['keys']  
            return await self.client.is_initialized() 
        return True

    async def unseal(self, keys:list = None) -> bool: 
        if keys is None: 
            keys = self.keys
        if (await self.client.is_sealed()) and keys is not None :
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

    async def createEngine(self, path:str) -> bool: 
        try:
            await self.client.enable_secret_backend(backend_type='kv', mount_point=path, options={'version':1})
            return True
        except Exception: 
            return False 

    async def disableEngine(self, path:str) -> bool  : 
        try:
            response = await self.client.disable_secret_backend(mount_point=path)
            return True
        except Exception: 
            return False 

    async def writeOrUpdate(self, mount:str, path:str, data:dict) -> bool: 
        try: 
            answer = await self.client.write(mount + "/" + path, **data)
            return True
        except Exception as e : 
            return False

        
    async def readAndRemove(self, mount:str, path:str) -> dict: 
        try: 
            data = await self.client.read(path=mount + "/" + path)
            ret = data['data']
 
            await self.client.delete(path = mount + "/" + path)
            return ret

        except Exception: 
            return None 

    async def remove(self, mount:str, path:str) -> bool: 
        try:  
            await self.client.delete(path = mount + "/" + path)
            return True
        except Exception: 
            return False 

    async def read(self, mount:str, path:str) -> dict: 
        try: 
            data = await self.client.read(path=mount + "/" + path)
            ret = data['data']
            return ret

        except Exception: 
            return None 

    
    
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
