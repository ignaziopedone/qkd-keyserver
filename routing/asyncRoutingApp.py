import qkdGraph
from lsaPacket import lsaPacket

from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from pymongo import UpdateOne
import asyncio
import aiohttp
import time 
import yaml 
import aioredis
import sys 
import logging

logging.basicConfig(filename='routing.log', filemode='w', level=logging.INFO)
logger = logging.getLogger('routing')

ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
redis_client : aioredis.Redis = None 
mongo_client : MongoClient = None 
http_client : aiohttp.ClientSession = None
config : dict = {}
cost_param = {'c0' : 100, 'c1' : -50, 'c2' : -25}
qkdm_availability = {}

def nextPowerOf2(x : int) -> int :  
    return 1 if x == 0 else 2**(x - 1).bit_length()

def routeCost(old: int, new: int, tot : int) -> int  : 
    global cost_param
    delta : int = ( new - old ) 
    cost : float = cost_param['c0'] + cost_param['c1'] * ( new / tot ) + cost_param['c2'] * ( delta / tot ) 
    return int(cost )

async def updateLinkCosts(): 
    global mongo_client, http_client , config, qkdm_availability, graph

    streams_collection = mongo_client[config['mongo_db']['db']]['key_streams']

    async for stream in (streams_collection.find({"qkdm" : {"$exists" : True}})) : 
        address = stream['qkdm']['address']
        async with http_client.get(f"http://{address['ip']}:{address['port']}/api/v1/qkdm/actions/get_id/{stream['_id']}") as ret: 
            ret_val = await ret.json()
            if ret_val['status'] == 0 and ret.status == 200: 
                new_av = ret_val['available_indexes']
            else: 
                new_av = 0    
            qkdm_id = stream['qkdm']['id']

            old_av = qkdm_availability[qkdm_id] if qkdm_id in qkdm_availability else new_av    
            qkdm_availability[qkdm_id] = new_av 
            cost = routeCost(old_av, new_av, stream['max_key_count'])
            graph.update_link(config['qks']['id'], stream['dest_qks']['id'], cost)
            logger.info(f"Costs updater: new cost {cost} from QKDM {qkdm_id}")

    return


async def receiveSocket(reader : asyncio.StreamReader, writer : asyncio.StreamWriter): 
    global mongo_client, config

    size = int.from_bytes(await reader.read(2), 'big') 
    packet = lsaPacket()

    read_size = nextPowerOf2(size)
    raw_packet = await reader.read(read_size)

    if len(raw_packet) == size :
        packet.decode(raw_packet)
    writer.close()
    await writer.wait_closed()


    if packet.data is not None and (packet.data['type'] == 'S' or packet.data['type'] == 'K'): 
        logger.info(f"Receiver: received packet {packet.data['type']} with source {packet.data['source']['ID']}")
        packet_srcID = packet.data['source']['ID']
        packet_routing = packet.data['routing']
        if packet_srcID != config['qks']['id']:
            if (packet_srcID) not in ksAddresses.keys() : 
                logger.warning(f"Receiver: packet from new source - qks {packet_srcID} added to the network")
                ksAddresses[packet_srcID] = {'ip' : packet_routing['address'], 'port' : packet_routing['port']}
                ksTimestamps[packet_srcID] = {'S' : 0.0, 'K' : 0.0}   
                qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers'] 
                qks_data = {"_id" : packet_srcID, "connected_SAE" : [], "neighbor_qks" : [], "address" : {"ip" : packet.data['source']['address'], "port" :  packet.data['source']['port']}, "routing_address" : {"ip" : packet_routing['address'], "port" :  packet_routing['port']}}
                qks_collection.insert_one(qks_data)
                graph.add_node(packet_srcID) 

            await forwardSocket(packet, writer.get_extra_info('peername')[0])
            up = await updateGraph(packet_srcID, packet.data['neighbors'], packet.data['timestamp'], ptype = packet.data['type']) 
            if up: 
                await updateRouting('force')

    else : 
        logger.warning(f"Receiver: Error in decoding a packet or unknown packet type")


async def sendSocket (ptype : str , ptime : float) :  
    me = config['qks']['id']
    d = graph.get_node(me).get_neighbors()
    neighbors = d.keys() 
    for ks in list(ksAddresses.keys()):
        addr = ksAddresses[ks] 
        if ks in neighbors:
            reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
            packet_data = { 'version' : 1, 
                'source' : {'ID' : me, 'address' : config['qks']['ip'], 'port' :  config['qks']['port']},
                'routing' : {'address' : config['routing']['ip'], 'port' :  config['routing']['port']}, 
                'timestamp' : ptime,
                'type' : ptype 
                }
            if ptype == 'S': 
                ids = graph.get_node(me).get_saes()
                neighbors = [{'ID' : id} for id in ids]
                packet_data['neighbors'] = neighbors
                packet = lsaPacket(packet_data)
            elif ptype == 'K': 
                ids = list(neighbors)
                costs = list(d.values())
                neighbors = [{'ID' : id, 'cost': cost } for id, cost in zip(ids, costs)]
                packet_data['neighbors'] = neighbors
                packet = lsaPacket(packet_data)

            p_enc = packet.encode()
            if (p_enc is not None):
                size = packet.get_dimension()
                writer.write(size.to_bytes(2, 'big'))
                writer.write(p_enc)
            writer.close() 
            await writer.wait_closed()
            logger.info(f"Sender: sent packet {packet_data['type']} to {ks} ")


async def forwardSocket(packet : lsaPacket, ip : str) : 

    global config , ksAddresses
    packet_srcID = packet.data['source']['ID']
    res = True if (packet_srcID != config['qks']['id'] and ksTimestamps[packet_srcID][packet.data['type']] < packet.data['timestamp']) else False 
    if res: 
        for ks in list(ksAddresses.keys()) :
            addr = ksAddresses[ks]
            if ks in graph.get_node(config['qks']['id']).get_neighbors().keys() and ip != addr['ip']:
                logger.info(f"Forwarding: forwarding packet {packet.data['type']} from {packet.data['source']['ID']}  to {ks}")
                reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
                size = packet.get_dimension()
                writer.write(size.to_bytes(2, 'big'))
                writer.write(packet.encode())                  
                writer.close() 
                

async def updateRouting(mode : str = 'standard') -> bool : 
    removed = False 
    global redis_client, graph
    threshold = time.time() - float(2*config['routing']['timer']) 
    removed = expireRoutes(threshold)
    await updateLinkCosts()

    if mode == 'force' or removed : 
        rts = graph.build_routing_tables(config['qks']['id'])
        old_rts = [x for x in (await redis_client.keys())] #read from redis 
        async with redis_client.pipeline() as pipe: 
            for rt, value in rts.items() :
                pipe.hset(name=rt, mapping=value)
                    
            
            for ort in old_rts: 
                if ort not in rts: 
                    pipe.delete(ort)
            res = await pipe.execute() 
        logger.info("Routing tables: updated to Redis")
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
                logger.info(f"Expiration: sae {sae} removed")

    
    for ks, ts in ksTimestamps.items(): 
        if ts['K'] < threshold : 
            for neighbor in graph.get_node(ks).get_neighbors().keys():
                if neighbor != config['qks']['id'] and ksTimestamps[neighbor]['K'] < threshold: 
                    graph.remove_link(ks, neighbor) 
                    logger.info(f"Expiration: link {ks}-{neighbor} removed")
                    removed = True
    return removed


async def updateGraph(src : str, neighbors : list, timestamp : float, ptype : str) -> bool :
    global mongo_client 
    up = False 
    
    qks_collection = mongo_client[config['mongo_db']['db']]['quantum_key_servers'] 
    mongo_requests = []

    ids = [ el['ID'] for el in neighbors]

    if ptype == 'S' and ksTimestamps[src][ptype] < timestamp : 
        up = True
        ksTimestamps[src][ptype] = timestamp
        old_saes = graph.get_node(src).get_saes() 
        for sae in ids: 
            if sae not in old_saes: 
                up = True
                graph.add_sae(sae, src)
                mongo_requests.append(UpdateOne({"_id" : src}, {"$addToSet" : {"connected_sae" : sae}}))
                logger.info(f"UpdateGraph: added  sae {sae} ")
                

        for sae in old_saes: 
            if sae not in ids:
                up = True
                graph.remove_sae(sae)  
                mongo_requests.append(UpdateOne({"_id" : src}, {"$pull" : {"connected_sae" : sae}}))
                logger.info(f"UpdateGraph: removed sae {sae} ")

    elif ptype == 'K' and ksTimestamps[src][ptype] < timestamp: 

        costs = [ el['cost'] for el in neighbors]

        ksTimestamps[src][ptype] = timestamp
        old_adj = graph.get_node(src).get_neighbors().keys() 
        for i, ks in enumerate(ids): 
            if ks not in old_adj : 
                up = True
                if ks not in ksTimestamps.keys(): 
                    graph.add_node(ks)
                    graph.add_link(src, ks, costs[i])
                    mongo_requests.append(UpdateOne({"_id" : src}, {"$addToSet" : {"neighbor_qks" : ks}}))
                    mongo_requests.append(UpdateOne({"_id" : ks}, {"$addToSet" : {"neighbor_qks" : src}}))
                elif timestamp > ksTimestamps[ks]['K']: 
                    graph.add_link(src, ks, costs[i])
                    logger.info(f"UpdateGraph: added link {ks}-{src} ")

                    
            else : # nodes in old list : update cost 
                if graph.update_link(src, ks, costs[i]): 
                    up = True

        for ks in old_adj: 
            if ks not in ids:
                if (ks not in ksTimestamps.keys()) or timestamp > ksTimestamps[ks]['K']:
                    up = True
                    graph.remove_link(src, ks)    
                    mongo_requests.append(UpdateOne({"_id" : src}, {"$pull" : {"neighbor_qks" : ks}}))
                    mongo_requests.append(UpdateOne({"_id" : ks}, {"$pull" : {"neighbor_qks" : src}}))
                    logger.info(f"UpdateGraph: removed link {ks}-{src} ")

    if mongo_requests != [] : 
        await qks_collection.bulk_write(mongo_requests) 

        
    return up


async def lsaUpdate() : 
    global config , graph, redis_client
    timer = config['routing']['timer']
    n = 0
    logger.warning(f"Timer: periodic update every {timer} s")
    while True: 
        await asyncio.sleep(timer)
        logger.info(f"Timer: update {n} - Redis keys: {await redis_client.keys()}")
        if (n % 10 == 0): 
            logger.warning(f"Timer: update {n} - Redis keys: {await redis_client.keys()}")
            #graph.print_nodes()
        if n == 0: 
            await updateRouting('force')
        else: 
            await updateRouting()
        await sendSocket('K', time.time())
        await sendSocket('S', time.time())
        n += 1

        
async def listenForChanges() : 
    global redis_client, config, graph, cost_param
    res = None 


    pubsub : aioredis.PubSub = redis_client.pubsub()
    await pubsub.psubscribe(f"{config['redis']['topic']}-**")
    logger.info("PubSUb listener: subscribed to redis topic")
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout = 0.1)
        if message is not None:
            logger.info(f"PubSUb listener: {message['channel']} => {message['data']}")
            action, name = message['data'].split("-")
            if message['channel'] == config['redis']['topic']+"-sae": 
                if action == "add": 
                    res = True if graph.add_sae(name, config['qks']['id']) is not None else False
                elif action == "remove": 
                    res = graph.remove_sae(name)
                if res:     
                    await updateRouting('force')
                    await sendSocket('S', time.time())


            elif message['channel'] == config['redis']['topic']+"-link":  
                if action == "add": 
                    res = graph.add_link(name, config['qks']['id'], cost_param['c0'])
                elif action == "remove": 
                    res = graph.remove_link(name, config['qks']['id']) 
                if res: 
                    await updateRouting('force')
                    await sendSocket('S', time.time())

            elif message['channel'] == config['redis']['topic']+"-qks": # new qks data received as id_routingIP_routingPort  
                if action == "add":
                    id, ip, port = name.split("_")
                    ksAddresses[id] = {'ip' : ip, 'port' : port}
                    ksTimestamps[id] = { 'K' : 0.0, 'S' : 0.0}
                    graph.add_node(id)
                    

async def initData() -> bool :
    # load server and SAE list from mongo and connect to redis 
    global config, redis_client , mongo_client, graph, cost_param, http_client
    redis_client = aioredis.from_url(f"redis://{config['redis']['host']}:{config['redis']['port']}/{config['redis']['db']}", username=config['redis']['user'], password=config['redis']['password'], decode_responses=True) 
    if not (await redis_client.ping()):
        return False

    await redis_client.flushdb()

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
                graph.add_link(n, qks['_id'], cost_param['c0'])

    init_data = {"connected_sae" : [], "neighbor_qks" : []}
    address_data = {"$set" : {"address" : {"ip" : config['qks']['ip'], "port" : config['qks']['port']}, "routing_address" : {"ip" : config['routing']['ip'], "port" : config['routing']['port']}}, "$setOnInsert" : init_data}
    qks_collection.update_one({"_id" : config['qks']['id']}, address_data, upsert=True )
    graph.add_node(config['qks']['id'])

    http_client = aiohttp.ClientSession()

    return True 


async def main() : 
    global config_file, config

    if len(sys.argv) == 2: 
        filename = sys.argv[1] 
    else: 
        filename =  "routing/config_files/config.yaml"
    config_file = open(filename, 'r')
    config = yaml.safe_load(config_file)
    config_file.close() 

    logger.info(f"starting ROUTING APP for server {config['qks']['id']}" )
    try : 
        res = await initData() 
        if not res: 
            logger.error("INIT ERROR: Redis unreachable or wrong configuration") 
            return 
    except Exception as e:
        logger.error(f"INIT ERROR: Redis unreachable or wrong configuration. EXCEPTION: {e}") 
        return 


    # running LSA thread
    lsaUpdateTask = asyncio.create_task(lsaUpdate())
    listenForChangesTask = asyncio.create_task(listenForChanges())
    logger.info(f"main : created tasks for timer and pubsub listener")
    server = await asyncio.start_server(receiveSocket, '0.0.0.0', int(config['routing']['port']))
    async with server:
        await server.serve_forever()

    lsaUpdateTask.cancel() 
    listenForChangesTask.cancel() 


if __name__ == "__main__":
    asyncio.run(main())

