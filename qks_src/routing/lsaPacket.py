import ipaddress

dims = { 
    1 : {
        'version' : 1, 
        'nAdj' : 1,
        'type' : 1,
        'srcID' : 32,
        'IP' : 4, 
        'port' : 2, 
        'time' : 18,
        'cost_list' : 1, 
        'id_list' : 32, 
    },
    2 : {
        'version' : 1, 
        'nAdj' : 1,
        'type' : 1,
        'srcID' : 32,
        'IP' : 4, 
        'port' : 2, 
        'time' : 18,
        'id_list' : 32, 
        'cost_list' : 1,
        'auth' :  64, 
        'options' :  64, 
    },

}



class lsaPacket() :
    def __init__(self, version, nAdj, ptype = None, srcID = None, srcIP = None, srcPort = None, ids = None, costs = None, time = 0.0, options = None, auth = None): 
        self.version : int = version 
        self.type : str = ptype  
        self.srcID : str = srcID 
        self.srcIP : str= srcIP 
        self.srcPort : int = srcPort 
        self.nAdj : int = nAdj 
        self.ids : list = ids 
        self.costs : list = costs
        self.time : str = time 

        if version == 2:
            self.auth = auth 
            self.options = options 


    def get_dimension(self) -> int:
        version = self.version
        pdim = 0

        if version not in dims: 
            return pdim

        for key, val in dims[version].items() : 
            if key == 'id_list' or key == 'cost_list' : 
                pdim += self.nAdj * val
            else : 
                pdim += val
        return pdim 
    
    
    def decode(self, rawbytes : bytearray) -> None:
        start = 0 
        version =self.version 

        self.type = rawbytes[start : start+dims[version]['type']].decode().replace('\0', '')
        start += dims[version]['type']
        
        self.srcID = rawbytes[start : start+dims[version]['srcID']].decode().replace('\0', '')
        start += dims[version]['srcID']

        self.srcIP = str(ipaddress.ip_address(int.from_bytes(rawbytes[start:start+dims[version]['IP']], 'big')))
        start += dims[version]['IP']
        self.srcPort = int.from_bytes(rawbytes[start:start+dims[version]['port']], 'big')
        start += dims[version]['port']

        self.ids = []
        self.costs = []
        for i in range(0,self.nAdj) : 
            next = start + dims[version]['id_list']
            next2 = next + dims[version]['cost_list']
            self.ids.append(rawbytes[start : next].decode().replace('\0', ''))
            self.costs.append(int.from_bytes(rawbytes[next : next2], 'big'))
            start = next2

        self.time = float(rawbytes[start : start+dims[version]['time']].decode().replace('\0', ''))

        if (self.version == 2):
            start += dims[version]['time']
            self.auth = rawbytes[start:start + dims[version]['auth']].decode().replace('\0', '')
        
            start += dims[version]['options']
            self.options = rawbytes[start:start + dims[version]['options']].decode().replace('\0', '')
        

    def encode(self) -> bytes : 
        version =self.version
        if self.nAdj != len(self.ids):
            return None 

        b = self.version.to_bytes(dims[version]['version'], 'big')
        b += self.nAdj.to_bytes(dims[version]['nAdj'], 'big')
         
        

        tmp = self.type
        if tmp is not None: 
            diff = dims[version]['type'] - len(tmp) 
            if (diff < 0):
                return None 
            elif (diff > 0):
                tmp += '\0' * diff
            b += tmp.encode()
        else:
            return None


        tmp = self.srcID
        if tmp is not None:
            diff = dims[version]['srcID'] - len(tmp)  
            if (diff < 0):
                return None 
            elif (diff > 0):
                tmp += '\0' * diff
            b += tmp.encode()
        else: 
            return None

        if self.srcIP is not None and self.srcPort is not None: 
            b += int(ipaddress.ip_address(self.srcIP)).to_bytes(dims[version]['IP'], 'big')
            b += int(self.srcPort).to_bytes(dims[version]['port'], 'big')
        else: 
            return None
        

        for i in range(0, self.nAdj) : 
            tmp = self.ids[i]
            c = self.costs[i]
            if tmp is not None and c is not None: 
                diff = dims[version]['id_list'] - len(tmp) 
                if (diff < 0):
                    return None 
                elif (diff > 0):
                    tmp += '\0' * diff
                b += tmp.encode() + c.to_bytes(dims[version]['cost_list'], 'big')
            else:
                return None
        
        tmp = str(self.time)
        if tmp is not None: 
            diff = dims[version]['time'] - len(tmp) 
            if (diff < 0):
                return None 
            elif (diff > 0):
                tmp += '\0' * diff
            b += tmp.encode()
        else: 
            return None

        if (self.version == 2) : 
            tmp = self.auth
            diff = dims[version]['auth'] - len(tmp)  
            if (diff < 0):
                return None 
            elif (diff > 0):
                tmp += '\0' * diff
            b += tmp.encode()

            tmp = self.options
            diff = dims[version]['options'] - len(tmp)
            if (diff < 0):
                return None 
            elif (diff > 0):
                tmp += '\0' * diff
            b += tmp.encode()

        return b

    def __str__(self) -> str:
        s = f'version : {self.version} | type : {self.type}  | nAdj : {self.nAdj} | srcID = {self.srcID} | srcAddress = {self.srcIP}:{self.srcPort} |time = {self.time} | IDs : {self.ids} | costs : {self.costs} |'
        if self.version == 2 :
            s += f' \n | auth : {self.auth} | \n options : {self.options}' 
        return s 
        
    