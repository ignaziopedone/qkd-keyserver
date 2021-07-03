
from os import fwalk
import qkdGraph
from lsaPacket import lsaPacket

from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from pymongo import UpdateOne
import asyncio
import time 
import yaml 
import aioredis
import async_timeout
import sys 


ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
redis_client : aioredis.Redis = None 
mongo_client : MongoClient = None 
config : dict = {}


async def receiveSocket(reader : asyncio.StreamReader, writer : asyncio.StreamWriter): 
    global mongo_client, config

    version = int.from_bytes(await reader.read(1), 'big')
    nAdj = int.from_bytes(await reader.read(1), 'big')
    packet = lsaPacket(version = version, nAdj = nAdj)

    read_size = nextPowerOf2(packet.get_dimension()-2) # 2 bytes already read
    raw_packet = await reader.read(read_size)

    if len(raw_packet) == packet.get_dimension()-2 :
        packet.decode(raw_packet)
    writer.close()
    await writer.wait_closed()

    #print(f"RECEIVE SOCKET: received a packet {packet.type} from {packet.srcID}")
    if packet.type == 'S' or packet.type == 'K': 

        if packet.srcID != config['qks']['id']:
            if (packet.srcID) not in ksAddresses.keys() : 
                ksAddresses[packet.srcID] = {'ip' : packet.routingIP, 'port' : packet.routingPort}
                ksTimestamps[packet.srcID] = {'S' : 0.0, 'K' : 0.0}   
                qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers'] 
                qks_data = {"_id" : packet.srcID, "connected_SAE" : [], "neighbor_qks" : [], "address" : {"ip" : packet.srcIP, "port" :  packet.srcPort}, "routing_address" : {"ip" : packet.routingIP, "port" :  packet.routingPort}}
                qks_collection.insert_one(qks_data)
                    
                graph.add_node(packet.srcID) 

            await forwardSocket(packet, writer.get_extra_info('peername'))
            await updateGraph(packet.srcID, packet.ids, packet.costs, packet.time, ptype = packet.type) 

    else : 
        print("ERROR: Error in decoding or unknown packet type")

async def sendSocket (me : str, ptype : str , ptime : float) :  
    d = graph.get_node(me).get_neighbors()
    neighbors = d.keys() 
    for ks in list(ksAddresses.keys()):
        addr = ksAddresses[ks] 
        if ks in neighbors:
            reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
            print(f"        SEND SOCKET: sending to {ks} a packet of type {ptype}")
            if ptype == 'S': 
                ids = graph.get_node(me).get_saes()
                costs = [0] * len(ids)
                packet = lsaPacket(version = 1, nAdj = len(ids), ptype = 'S', srcID = me, srcIP = config['qks']['ip'], srcPort = config['qks']['port'], routingPort=config['routing']['port'], routingIP=config['routing']['ip'], time = ptime, ids = ids, costs = costs)
            elif ptype == 'K': 
                ids = list(neighbors)
                costs = list(d.values())
                packet = lsaPacket(version = 1, nAdj = len(ids), ptype = 'K', srcID = me, srcIP = config['qks']['ip'], srcPort = config['qks']['port'], routingPort=config['routing']['port'], routingIP=config['routing']['ip'], time = ptime, ids = ids, costs = costs)
            
            p_enc = packet.encode()
            if (p_enc is not None):
                writer.write(p_enc)
            writer.close() 
            await writer.wait_closed()

async def forwardSocket(packet : lsaPacket, ip : str) : 
    global config 
    res = True if (packet.srcID != config['qks']['id'] and ksTimestamps[packet.srcID][packet.type] < packet.time) else False 
    if res: 
        for ks in list(ksAddresses.keys()) :
            addr = ksAddresses[ks]
            if ks in graph.get_node(config['qks']['id']).get_neighbors().keys() and packet.srcID != ks:
                #print(f"    FORWARD SOCKET: forwarding a packet of type {packet.type} to {ks}")
                reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
                writer.write(packet.encode())                  
                writer.close()
                await writer.wait_closed() 

def nextPowerOf2(x : int) -> int :  
    return 1 if x == 0 else 2**(x - 1).bit_length()

async def updateRouting(mode : str = 'standard') -> bool : 
    removed = False 
    global redis_client

    threshold = time.time() - float(2*config['routing']['timer']) 
    removed = expireRoutes(threshold)
    
    if mode == 'force' or removed : 
        rts = graph.build_routing_tables(config['qks']['id'])
        old_rts = [x for x in (await redis_client.keys())] #read from redis 
        async with redis_client.pipeline() as pipe: 
            for rt, value in rts.items() :
                for k, el in value.items(): 
                    pipe.hset(name=rt, key = k, value = el)
            
            for ort in old_rts: 
                if ort not in rts: 
                    pipe.delete(ort)
            res = await pipe.execute() 
        return True
    return False

def expireRoutes(threshold : float) -> bool : 
    global config 
    removed = False

    for ks, ts in ksTimestamps.items(): 
        if ts['S'] < threshold : 
            removed = True
            for sae in graph.get_node(ks).get_saes(): 
                graph.remove_sae(sae)

    
    for ks, ts in ksTimestamps.items(): 
        if ts['K'] < threshold : 
            for neighbor in graph.get_node(ks).get_neighbors().keys():
                if neighbor != config['qks']['id'] and ksTimestamps[neighbor]['K'] < threshold: 
                    graph.remove_link(ks, neighbor) 
                    print(f"REMOVED LINK: {ks} - {neighbor}")
                    removed = True
    return removed

async def updateGraph(src : str, ids : list, costs : float, timestamp : float, ptype : str) -> bool :
    global mongo_client 
    up = False 
    
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers'] 
    mongo_requests = []

    if ptype == 'S' and ksTimestamps[src][ptype] < timestamp : 
        up = True
        ksTimestamps[src][ptype] = timestamp
        old_saes = graph.get_node(src).get_saes() 
        for sae in ids: 
            if sae not in old_saes: 
                up = True
                graph.add_sae(sae, src)
                mongo_requests.append(UpdateOne({"_id" : src}, {"$addToSet" : {"connected_sae" : sae}}))
                

        for sae in old_saes: 
            if sae not in ids:
                up = True
                graph.remove_sae(sae)  
                mongo_requests.append(UpdateOne({"_id" : src}, {"$pull" : {"connected_sae" : sae}}))

    elif ptype == 'K' and ksTimestamps[src][ptype] < timestamp: 
        ksTimestamps[src][ptype] = timestamp
        old_adj = graph.get_node(src).get_neighbors().keys() 
        for i, ks in enumerate(ids): 
            if ks not in old_adj : 
                up = True
                if ks not in ksTimestamps.keys(): 
                    graph.add_node(ks)
                    graph.add_link(src, ks, costs[i])
                    mongo_requests.append(UpdateOne({"_id" : src}, {"$addToSet" : {"neighbor_qks" : ks}}))
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
                    mongo_requests.append(UpdateOne({"_id" : src}, {"$pull" : {"neighbor_qks" : ks}}))

    if mongo_requests != [] : 
        await qks_collection.bulk_write(mongo_requests) 

    return up

async def lsaUpdate() : 
    global config , graph
    timer = config['routing']['timer']
    me = config['qks']['id']
    n = 0
    print(f"Started task for periodic update every {timer} s")
    while True: 
        n += 1
        await asyncio.sleep(timer)
        print(f"LSA UPDATE : sending periodic update {n}")
        await updateRouting()
        await sendSocket(me, 'K', time.time())
        await sendSocket(me, 'S', time.time())
        

async def listenForChanges() : 
    print("Started task subscribed to redis topic")
    global redis_client, config
    res = None 
    pubsub : aioredis.PubSub = redis_client.pubsub()
    await pubsub.psubscribe(f"{config['redis']['topic']}-**")

    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True)
        if message is not None:
            print(f"LISTEN FOR CHANGES: Subscribe message received from {message['channel']} => {message['data']}")
            action, name = message['data'].split("-")
            if message['channel'] == config['redis']['topic']+"-sae": 
                if action == "add": 
                    res = True if graph.add_sae(name, config['qks']['id']) is not None else False
                elif action == "remove": 
                    res = graph.remove_sae(name)
                print(f" CHANGES : sae {res}")
                if res:     
                    await updateRouting('force')
                    await sendSocket(config['qks']['id'], 'S', time.time())


            elif message['channel'] == config['redis']['topic']+"-link":  
                if action == "add": 
                    res = graph.add_link(name, config['qks']['id'], 1)
                elif action == "remove": 
                    res = graph.remove_link(name, config['qks']['id']) 
                print(f" CHANGES : link {res}")
                if res: 
                    await updateRouting('force')
                    await sendSocket(config['qks']['id'], 'S', time.time())
            


        


async def initData() -> bool :
    # load server and SAE list from mongo and connect to redis 
    global config, redis_client , mongo_client, graph
    redis_client = aioredis.from_url(f"redis://{config['redis']['host']}:{config['redis']['port']}/{config['redis']['db']}", username=config['redis']['user'], password=config['redis']['password'], decode_responses=True) 
    if not (await redis_client.ping()): 
        return False

    await redis_client.flushdb(config['redis']['db'])

    try: 
        mongo_client = MongoClient(f"mongodb://{config['mongo_db']['user']}:{config['mongo_db']['password']}@{config['mongo_db']['host']}:{config['mongo_db']['port']}/{config['mongo_db']['db']}?authSource={config['mongo_db']['auth_src']}")
        qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers'] 

        qks_cursor = qks_collection.find()
        
        async for qks in qks_cursor:  
            if qks['_id'] != config['qks']['id']: 
                ksAddresses[qks['_id']] = qks['routing_address']
                ksTimestamps[qks['_id']] = { 'K' : 0.0, 'S' : 0.0}
            graph.add_node(qks['_id'])
            if 'connected_sae' in qks: 
                for sae in qks['connected_sae']: 
                    graph.add_sae(sae, qks['_id'])
            if 'neighbor_qks' in qks: 
                for n in qks['neighbor_qks']: 
                    graph.add_node(n)
                    graph.add_link(n, qks['_id'], 1)

    except Exception: 
        return False 

    print(f"INIT GRAPH: {graph}")
    graph.print_nodes()

    return True 


async def main() : 
    global config_file, config

    if len(sys.argv) == 2: 
        filename = sys.argv[1] 
    else: 
        filename =  "routing/config2.yaml"
    config_file = open(filename, 'r')
    config = yaml.safe_load(config_file)
    config_file.close() 

    print(f"starting ROUTING APP: {config['qks']['id']}" )
    try : 
        res = await initData() 
        if not res: 
            print("ERROR IN INIT ROUTING ALGORITHM")
            return 
    except Exception as e:
        print("ERROR IN INIT ROUTING ALGORITHM")
        return 


    # running LSA thread

    lsaUpdateTask = asyncio.create_task(lsaUpdate())
    listenForChangesTask = asyncio.create_task(listenForChanges())

    server = await asyncio.start_server(receiveSocket, '0.0.0.0', int(config['routing']['port']))
    async with server:
        await server.serve_forever()

    lsaUpdateTask.cancel() 
    listenForChangesTask.cancel() 


if __name__ == "__main__":
    asyncio.run(main())

