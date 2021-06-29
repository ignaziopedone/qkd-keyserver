import qkdGraph
from lsaPacket import lsaPacket

from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
import asyncio
import time 
import yaml 
import aioredis
import async_timeout


ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
redis_client : aioredis.Redis = None 
mongo_client : MongoClient = None 

config_file = open("routing/config.yaml", 'r')
config : dict = yaml.safe_load(config_file)
config_file.close()


async def receiveSocket(reader : asyncio.StreamReader, writer : asyncio.StreamWriter):
    
    version = int.from_bytes(await reader.read(1), 'big')
    nAdj = int.from_bytes(await reader.read(1), 'big')
    packet = lsaPacket(version = version, nAdj = nAdj)

    read_size = next_power_of_2(packet.get_dimension()-2) # 2 bytes already read
    raw_packet = await reader.read(read_size)

    if len(raw_packet) == packet.get_dimension()-2 :
        packet.decode(raw_packet)
    writer.close()
    await writer.wait_closed()

    t_arr = time.time() 
    if packet.type == 'S' or packet.type == 'K': 

        if (packet.srcID) not in ksAddresses.keys(): 
            ksAddresses[packet.srcID] = {'ip' : packet.srcIP, 'port' : packet.srcPort}
            ksTimestamps[packet.srcID] = {'S' : 0.0, 'K' : 0.0}       
            graph.add_node(packet.srcID) 

        await forwardSocket(packet, writer.get_extra_info('peername'))
        updategraph(packet.srcID, packet.ids, packet.costs, packet.time, ptype = packet.type) 

    else : 
        print("ERROR: Error in decoding or unknown packet type")

async def sendSocket (me : str, ptype : str , ptime : float) :  
    d = graph.get_node(me).get_neighbors()
    neighbors = d.keys() 

    ksTimestamps[me][ptype] = ptime

    for ks in list(ksAddresses.keys()):
        addr = ksAddresses[ks] 
        if ks in neighbors:
            reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])

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
                writer.write(p_enc)
            writer.close() 
            await writer.wait_closed()

async def forwardSocket(packet : lsaPacket, ip : str) : 

    res = True if (ksTimestamps[packet.srcID][packet.type] < packet.time) else False 
    if res: 
        for ks in list(ksAddresses.keys()) :
            addr = ksAddresses[ks]
            if ks in graph.get_node(config['qks']['id']).get_neighbors().keys() and ip != addr['ip']:
                
                reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
                writer.write(packet.encode())                  
                writer.close()
                await writer.wait_closed() 

def next_power_of_2(x : int) -> int :  
    return 1 if x == 0 else 2**(x - 1).bit_length()

# TODO : CHECK REDIS USAGE
def updateRouting(mode : str = 'standard') -> bool : 
    removed = False 
    global redis_client


    threshold = time.time() - float(2*config['routing']['timer']) 
    removed = expire_routes(threshold)

    if mode == 'force' or removed : 
        rts = graph.build_routing_tables(config['qks']['id'])
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

def expire_routes(threshold : float) -> bool : 
    removed = False

    for ks, ts in ksTimestamps.items(): 
        if ts['S'] < threshold : 
            removed = True
            for sae in graph.get_node(ks).get_saes(): 
                graph.remove_sae(sae)

    
    for ks, ts in ksTimestamps.items(): 
        if ts['K'] < threshold : 
            for neighbor in graph.get_node(ks).get_neighbors().keys():
                if ksTimestamps[neighbor]['K'] < threshold: 
                    graph.remove_link(ks, neighbor) 
                    removed = True

    return removed

def updategraph(src : str, ids : list, costs : float, timestamp : float, ptype : str) -> bool :
    up = False 

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

async def lsaUpdate() : 
    print("Started task for periodic update")
    global config 
    timer = config['routing']['timer']
    me = config['qks']['id']
    while True: 
        asyncio.sleep(timer)
        sendSocket(me, 'K', time.time())
        sendSocket(me, 'S', time.time())
        updateRouting()

# TODO
async def listenForChanges() : 
    print("Started task subscribed to redis topic")
    global redis_client, config

    pubsub : aioredis.PubSub = redis_client.pubsub()
    await pubsub.subscribe(config['redis']['topic'])

    while True:
        try:
            async with async_timeout.timeout(1):
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    print(f"    Subscribe message received: {message['data']}")
                await asyncio.sleep(0.01)
        except asyncio.TimeoutError:
            pass 
    

# TODO 
async def initData() -> bool :
    # load server and SAE list from mongo and connect to redis 
    global config, redis_client 
    redis_client : aioredis.Redis = aioredis.from_url(f"redis://{config['redis']['host']}:{config['redis']['port']}", username=config['redis']['user'], password=config['redis']['password'], decode_responses=True)
    res = redis_client.ping()
    
    if res != "PONG" : 
        return False 

    ''' 
    graph.add_node(config['qks']['id'])
    for ks in ksAddresses.keys() :
        ksTimestamps[ks] = { 'K' : 0.0, 'S' : 0.0}
        if ks != config['qks']['id']:  
            graph.add_node(ks)
            graph.add_link(config['qks']['id'], ks, 1)
    '''


async def main() : 
    global config_file

    config_file = open("qks_src/config_files/config.yaml", 'r')
    config : dict = yaml.safe_load(config_file)
    config_file.close() 

    print(f"starting ROUTING APP: {config['qks']['id']}" )
    try : 
        res = await initData() 
        if not res: 
            print("ERROR IN INIT ROUTING ALGORITHM")
            return 
    except Exception:
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

