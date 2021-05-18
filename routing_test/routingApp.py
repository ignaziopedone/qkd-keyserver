import qkdGraph
from lsaPacket import lsaPacket
import sys
import time
from threading import Thread, Event, Lock
import socket
import ast # dictionary reading modules 
from random import randint, uniform
import redis


me = ""
ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
redis_client = None 
lock = {'K' : Lock(), 'S' : Lock(), 'R' : Lock()}
timer = 10


def next_power_of_2(x):  
    return 1 if x == 0 else 2**(x - 1).bit_length()


def serverSocket(port): 
    s = socket.socket() 
    s.bind(('0.0.0.0', int(port)))         
    print ("SERVER: socket  binded to %s" %(port)) 
    s.listen(5) 

    while True: 
        c, addr = s.accept()     
        t = Thread(target=receiveSocket, args=(c,addr[0],)).start() 


def receiveSocket(socket_client, ip):
    version = int.from_bytes(socket_client.recv(1), 'big')
    nAdj = int.from_bytes(socket_client.recv(1), 'big')
    packet = lsaPacket(version = version, nAdj = nAdj)

    read_size = next_power_of_2(packet.get_dimension()-2) # 2 bytes already read
    raw_packet = socket_client.recv(read_size)

    if len(raw_packet) == packet.get_dimension()-2 :
        packet.decode(raw_packet)
    socket_client.close()

    t_arr = time.time() 
    if packet.type == 'S' or packet.type == 'K': 
        with lock['K'] : 
            if (packet.srcID) not in ksAddresses.keys(): 
                ksAddresses[packet.srcID] = {'ip' : packet.srcIP, 'port' : packet.srcPort}
                ksTimestamps[packet.srcID] = {'S' : 0.0, 'K' : 0.0}       
                graph.add_node(packet.srcID) 

        forwardSocket(packet, ip)
        updategraph(packet.srcID, packet.ids, packet.costs, packet.time, ptype = packet.type) 

    else : 
        print("ERROR: Error in decoding or unknown packet type")
        

def sendSocket (me, ptype, ptime) :  
    d = graph.get_node(me).get_neighbors()
    neighbors = d.keys() 


    ksTimestamps[me][ptype] = ptime

    for ks in list(ksAddresses.keys()):
        addr = ksAddresses[ks] 
        if ks in neighbors:
            s = socket.socket()                      
            s.connect((addr['ip'], addr['port'])) 

            if ptype == 'S': 
                ids = graph.get_node(me).get_saes()
                costs = [0] * len(ids)
                packet = lsaPacket(version = 1, nAdj = len(ids), ptype = 'S', srcID = me, srcIP = ksAddresses[me]['ip'], srcPort = ksAddresses[me]['port'], time = ptime, ids = ids, costs = costs)
            elif ptype == 'K': 
                ids = list(neighbors)
                costs = list(d.values())
                packet = lsaPacket(version = 1, nAdj = len(ids), ptype = 'K', srcID = me, srcIP = ksAddresses[me]['ip'], srcPort = ksAddresses[me]['port'], time = ptime, ids = ids, costs = costs)
            
            p_enc = packet.encode()
            if (p_enc is not None):
                s.sendall(p_enc)
                s.close() 


def forwardSocket(packet, ip) : 
    with lock[packet.type]: 
        res = True if (ksTimestamps[packet.srcID][packet.type] < packet.time) else False 

    if res: 
        for ks in list(ksAddresses.keys()) :
            addr = ksAddresses[ks]
            if ks in graph.get_node(me).get_neighbors().keys() and ip != addr['ip']:
                
                s = socket.socket()                      
                s.connect((addr['ip'], addr['port'])) 
                s.sendall(packet.encode())
                s.close() 


def updategraph(src, ids, costs, timestamp, ptype) :
    up = False 

    with lock[ptype]: 
        if ptype == 'S' and ksTimestamps[src][ptype] < timestamp : 
            up = True
            ksTimestamps[src][ptype] = timestamp
            old_saes = graph.get_node(src).get_saes() 
            for sae in ids: 
                if sae not in old_saes: 
                    up = True
                    graph.add_sae(sae, src)

            for sae in old_saes: 
                if sae not in ids:
                    up = True
                    graph.remove_sae(sae)  


        elif ptype == 'K' and ksTimestamps[src][ptype] < timestamp: 
            ksTimestamps[src][ptype] = timestamp
            old_adj = graph.get_node(src).get_neighbors().keys() 
            for i, ks in enumerate(ids): 
                if ks not in old_adj : 
                    up = True
                    if ks not in ksTimestamps.keys(): 
                        graph.add_node(ks)
                        graph.add_link(src, ks, costs[i])
                    elif timestamp > ksTimestamps[ks]['K']: 
                        graph.add_link(src, ks, costs[i])
                else : # nodes in old list : update cost 
                    if graph.update_link(src, ks, costs[i]): 
                        up = True

            for ks in old_adj: 
                if ks not in ids:
                    if (ks not in ksTimestamps.keys()) or timestamp > ksTimestamps[ks]['K']:
                        up = True
                        graph.remove_link(src, ks)    
    return up

def updateRouting(mode = 'standard'): 
    removed = False 
    global redis_client

    with lock['R'] : 
        threshold = time.time() - float(2*timer) 
        removed = expire_routes(threshold)

        if mode == 'force' or removed : 
            rts = graph.build_routing_tables(me)
            old_rts = [x.decode() for x in redis_client.keys()] #read from redis 
            
            with redis_client.pipeline() as pipe: 
                for rt, value in rts.items() :
                    for k, el in value.items(): 
                        pipe.hset(name=rt, key = k, value = el)
                
                for ort in old_rts: 
                    if ort not in rts: 
                        pipe.delete(ort)
                pipe.execute() 

            return True
    return False


def expire_routes(threshold) : 
    removed = False
    with lock['S']: 
        for ks, ts in ksTimestamps.items(): 
            if ts['S'] < threshold : 
                removed = True
                for sae in graph.get_node(ks).get_saes(): 
                    graph.remove_sae(sae)

    with lock['K']: 
        for ks, ts in ksTimestamps.items(): 
            if ts['K'] < threshold : 
                for neighbor in graph.get_node(ks).get_neighbors().keys():
                    if ksTimestamps[neighbor]['K'] < threshold: 
                        graph.remove_link(ks, neighbor) 
                        removed = True

    return removed


class lsaThread(Thread): 
    def __init__(self, me, timer):
        Thread.__init__(self)
        self.me = me
        self.timer = timer 

    def random_update(self): 
            r_act = randint(0, 3)

            if r_act == 0: 
                sae = self.me + str(randint(0,10)) 
                if  graph.add_sae(sae, self.me) is not None:
                    sendSocket(self.me, 'S', time.time())

            elif r_act == 1: 
                saes = graph.get_node(self.me).get_saes() 
                if (len(saes) > 1) :
                    sae = saes[randint(0, len(saes)-1)]
                    if graph.remove_sae(sae) : 
                        sendSocket(self.me, 'S', time.time())

            elif r_act == 2: 
                cost = randint(1,10)
                nodes = list(ksAddresses.keys() )
                dst = nodes[randint(0, len(nodes)-1)]
                if graph.add_link(self.me, dst, cost): 
                    sendSocket(self.me, 'K', time.time())

            elif r_act == 3: 
                links = list(graph.get_node(self.me).get_neighbors().keys()) 
                if (len(links) > 1) :
                    dst = links[randint(0, len(links)-1)]
                    if graph.remove_link(self.me, dst) : 
                        sendSocket(self.me, 'K', time.time())

    def run(self):
        time.sleep(randint(0,self.timer))
        print("     TIMER: LSA THREAD STARTED")
        while True:
            time.sleep(self.timer/2)
            sendSocket(self.me, 'K', time.time())
            sendSocket(self.me, 'S', time.time())
            updateRouting() #standard update

            time.sleep(self.timer/2)
            self.random_update() 
            updateRouting(mode='force')

            '''for key in graph.get_saes():  
                val = {k.decode() : v.decode() for k,v in redis_client.hgetall(key).items() }
                if val : #not an empty dict -> not a sae attatched to me 
                    print(key, val)'''


            

def main(argv) : 
    global ksAddresses, graph, ksTimestamps, me, timer, redis_client
    me = argv[1]
    file = open(f"init_files/connections.json", "r")
    contents = file.read()
    ksAddresses = ast.literal_eval(contents)[me]
    file.close()

    graph.add_node(me)
    for ks in ksAddresses.keys() :
        ksTimestamps[ks] = { 'K' : 0.0, 'S' : 0.0}
        if ks != me:  
            graph.add_node(ks)
            graph.add_link(me, ks, 1)

    print(f"starting server: \n {graph.get_node(me)}" )

    # running LSA thread
    redis_client = redis.Redis() 

    lsaThread(me, timer).start()


    # running socket server 
    serverPort = ksAddresses[me]['port']
    serverSocket(serverPort)


    

if __name__ == "__main__":
    if len(sys.argv) != 2 : 
        print("USAGE: python routingApp.py <server name> ")
    else:
        main(sys.argv)

