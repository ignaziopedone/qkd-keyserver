import json
element_list = ["version", "type", "source", "routing", "neighbors", "timestamp", "auth"]

dims = {
    'version' : 1, 
    'nAdj' : 1,
    'type' : 1,
    'srcID' : 32,
    'address' : 32, 
    'port' : 2, 
    'timestamp' : 18,
    'id_list' : 32, 
    'cost_list' : 1,
    'auth' :  64}
    

class lsaPacket(): 
    def __init__(self, data : dict = {}, size : int = None) -> int: 
        self.data = data
        self.json_size = size

    def get_dimension(self) -> int: 
        if self.json_size is None:  
            self.json_size = len(json.dumps(self.data))

        return self.json_size

    def decode(self, rawbytes : bytearray) -> None: 
        raw_string = rawbytes.decode()
        self.data = json.loads(raw_string)
        if not all(key in self.data for key in element_list) : 
            self.data = None

    def encode(self) -> bytes: 
        if all(key in self.data for key in element_list) : 
            raw_string = json.dumps(self.data)
            return raw_string.encode() 
        else: 
            return None

    def __str__(self) -> str: 
        s = f'version : {self.data["version"]} | type : {self.data["type"]}  | n_connected : {len(self.data["neighbors"])} | source = {self.data["source"]} | time = {self.data["timestamp"]} | neighbors : {self.data["neighbors"]} |'
        return s

class lsaPacketRaw(): 
    def __init__(self, data:dict = {}, size: int= None): 
        self.data = data
        self.raw_size = size

    def get_dimension(self) -> int: 
        if self.raw_size is None:
            pdim = 0
            for key, val in dims: 
                if key == 'id_list' or key == 'cost_list' : 
                    pdim += len(self.data['neighbors']) * val
                elif key == "IP" or key == "port": 
                    pdim += 2*val # qks and routing ip/port
                else : 
                    pdim += val
            self.raw_size = pdim
        return self.raw_size

    def encode(self) -> bytes : 
        if not all(key in self.data for key in element_list): 
            return None 
        if not all (key in self.data['source'] for key in ["ID", "address", "port"]) and not all (key in self.data['routing'] for key in ["address", "port"]) : 
            return None 

        nAdj = len(self.data['neighbors'])
        b = int(self.data['version']).to_bytes(dims['version'], 'big')
        b += nAdj.to_bytes(dims['nAdj'], 'big')
         

        tmp = str(self.data['type'])
        if (len(tmp) != dims['type']):
            return None 
        b += tmp.encode()

        tmp = str(self.data['source']['ID'])
        diff = dims['srcID'] - len(tmp)  
        if (diff < 0):
            return None 
        tmp += '\0' * diff
        b += tmp.encode()

        tmp = str(self.data['source']['address'])
        diff = dims['address'] - len(tmp)  
        if (diff < 0):
            return None 
        tmp += '\0' * diff
        b += tmp.encode()
        b += int(self.data['source']['port']).to_bytes(dims['port'], 'big')

        tmp = str(self.data['routing']['address'])
        diff = dims['address'] - len(tmp)  
        if (diff < 0):
            return None 
        tmp += '\0' * diff
        b += tmp.encode()
        b += int(self.data['routing']['port']).to_bytes(dims['port'], 'big')


        for n in self.data['neighbors'] : 
            tmp = str(n['ID'])
            diff = dims['id_list'] - len(tmp) 
            if (diff < 0):
                return None 
            tmp += '\0' * diff
            if 'cost' in n: 
                b += tmp.encode() + int(n['cost']).to_bytes(dims['cost_list'], 'big')
            else:
                b += tmp.encode()

        
        tmp = str(self.data['timestamp'])
        diff = dims['timestamp'] - len(tmp) 
        if (diff < 0):
            return None 
        tmp += '\0' * diff
        b += tmp.encode()


        tmp = str(self.data['auth'])
        diff = dims['auth'] - len(tmp)  
        if (diff < 0):
            return None 
        tmp += '\0' * diff
        b += tmp.encode()

        return b

    def decode(self, rawbytes : bytearray) -> None: 
        start = 0 
        self.data['version'] = int.from_bytes(rawbytes[start : start + dims['version']], 'big')
        start += dims['version']
        nAdj = int.from_bytes(rawbytes[start : start + dims['nAdj']], 'big')
        start += dims['nAdj']

        self.data['type'] = rawbytes[start : start+dims['type']].decode().replace('\0', '')
        start += dims['type']
        
        self.data['source'] = {}
        self.data['source']['ID'] = rawbytes[start : start+dims['srcID']].decode().replace('\0', '')
        start += dims['srcID']

        self.data['source']['address'] = rawbytes[start:start+dims['address']].decode().replace('\0', '')
        start += dims['address']
        self.data['source']['port'] = int.from_bytes(rawbytes[start:start+dims['port']], 'big')
        start += dims['port']

        self.data['routing'] = {}
        self.data['routing']['address'] = rawbytes[start:start+dims['address']].decode().replace('\0', '')
        start += dims['address']
        self.data['routing']['port'] = int.from_bytes(rawbytes[start:start+dims['port']], 'big')
        start += dims['port']

        self.data['neighbors'] = []
        for i in range(0,nAdj) : 
            neigh_i = {}
            next = start + dims['id_list']
            
            neigh_i['ID'] = (rawbytes[start : next].decode().replace('\0', ''))
            if self.data['type'] == 'K':
                next2 = next + dims['cost_list']
                neigh_i['cost'] = (int.from_bytes(rawbytes[next : next2], 'big'))
            start = next2 if self.data['type'] == 'K' else next 
            self.data['neighbors'].append(neigh_i)
            

        self.data['timestamp'] = float(rawbytes[start : start+dims['timestamp']].decode().replace('\0', ''))
        start += dims['timestamp']
        self.data['auth'] = rawbytes[start:start + dims['auth']].decode().replace('\0', '')
        