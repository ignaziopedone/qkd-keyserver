import json
element_list = ["version", "type", "source", "routing", "neighbors", "timestamp"]

class lsaPacket(): 
    def __init__(self, data : dict = {}, json_size : int = None) -> int: 
        self.data = data
        self.json_size = json_size

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