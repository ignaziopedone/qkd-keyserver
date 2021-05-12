import hvac 

class Client() : 
    def __init__(self, address, port, token = None, tls = False, keys = []): 
        if tls: 
            self.client = hvac.Client(url='https://'+address+":"+str(port), verify=False)
        else: 
            self.client = hvac.Client(url='http://'+address+":"+str(port))
        self.client.token = token
        self.keys = keys

    def initialize(self, shares, threshold) : 
        if not self.client.sys.is_initialized():
            result = self.client.sys.initialize(shares, threshold)
            self.client.token = result['root_token']
            self.keys = result['keys']  
            return self.client.sys.is_initialized() 
        return True

    def unseal(self, keys = None): 
        if keys is None: 
            keys = self.keys
        if self.client.sys.is_sealed() and keys is not None :
            self.client.sys.submit_unseal_keys(keys)
        return not self.client.sys.is_sealed() 
    
    def seal(self): 
        if not self.client.sys.is_sealed() :
            self.client.sys.seal()
        return self.client.sys.is_sealed() 
            
    def connect(self, token = None) : 
        if token is not None: 
            self.client.token = token

        if not self.client.sys.is_initialized(): 
            return False

        return self.client.is_authenticated()

    def approle_login(self, role_id, secret_id): 
        try: 
            self.client.auth.approle.login(role_id=role_id, secret_id=secret_id) 
            return True
        except: 
            return False

    def createEngine(self, path) : 
        try:
            self.client.sys.enable_secrets_engine(backend_type='kv', path=path, options={'version':1})
            return True
        except: 
            return False 

    def disableEngine(self, path) : 
        try:
            response = self.client.sys.disable_secrets_engine(path=path)
            return True
        except: 
            return False 

    def writeOrUpdate(self, mount, path, data) : 
        if type(data) is dict:
            try: 
                answer = self.client.secrets.kv.v1.create_or_update_secret(mount_point=mount, path=path, secret=data)
                return True
            except: 
                return False
        
    def readAndRemove(self, mount, path, id=None) : 
        try: 
            data = self.client.secrets.kv.v1.read_secret(path=path, mount_point=mount)
            if id is not None and id in data['data']: 
                val = data['data'].pop(id, None) 
                ret = {id : val}
            else: 
                ret = data['data']

            if id is None or not data:  #take all data or the last id  
                self.client.secrets.kv.v1.delete_secret(path = path, mount_point=mount)
            else: 
                self.client.secrets.kv.v1.create_or_update_secret(mount_point=mount, path=path, secret=data['data'])

            return ret
        except: 
            return None 
    
    def createUser(self, id): 
        auth_methods = self.client.sys.list_auth_methods()['data'].keys()
        if 'approle/' not in auth_methods: 
            self.client.sys.enable_auth_method(method_type='approle')

        self.createEngine(id)

        policy = """
            path "%s/*" {
            capabilities = ["create", "read", "update", "delete", "list"]
            }""" % id

        try: 
            self.client.sys.create_or_update_policy(name=id, policy=policy)
            self.client.auth.approle.create_or_update_approle(role_name=id, token_policies=[id], token_type='service')

            response = {}
            response["role_id"] = self.client.auth.approle.read_role_id(role_name='module1')["data"]["role_id"]
            response["secret_id"] = self.client.auth.approle.generate_secret_id(role_name='module1')["data"]["secret_id"]
            return response
        except: 
            return None
