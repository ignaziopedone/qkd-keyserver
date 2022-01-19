import qkdGraph
from lsaPacket import lsaPacket

import asyncio
import aiohttp
import time 
import yaml 
import sys 
import logging
from random import randint

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('routing')
counter = 0
ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
http_client : aiohttp.ClientSession = None
config : dict = {}
cost_param = {'c0' : 100, 'c1' : -50, 'c2' : -25}

def nextPowerOf2(x : int) -> int :  
    return 1 if x == 0 else 2**(x - 1).bit_length()

async def updateLinkCosts(): 
    return


async def receiveSocket(reader : asyncio.StreamReader, writer : asyncio.StreamWriter): 
    global config, counter

    size = int.from_bytes(await reader.read(2), 'big') 
    packet = lsaPacket()

    try: 
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
                    graph.add_node(packet_srcID) 

                await forwardSocket(packet, writer.get_extra_info('peername')[0])
                up = await updateGraph(packet_srcID, packet.data['neighbors'], packet.data['timestamp'], ptype = packet.data['type']) 
                if up: 
                    await updateRouting('force')
                    if counter < 2000: 
                        logger.debug(f"TIMING {counter}: {packet.data['type']} {packet.data['hop']} {time.time() - packet.data['timestamp']}")
                        counter+=1

        else : 
            logger.warning(f"Receiver: Error in decoding a packet or unknown packet type")
    except Exception as e: 
        logger.error(f"Exception in receiveSocket: {e}")


async def sendSocket (ptype : str , ptime : float) :  
    me = config['qks']['id']
    d = graph.get_node(me).get_neighbors()
    neighbors = list(d.keys()) 
    logger.info(f"Current neighbors: {neighbors}, QKS in the network: {list(ksAddresses.keys())}")
    for ks in list(ksAddresses.keys()):
        try: 
            addr = ksAddresses[ks] 
            if ks in neighbors:
                logger.info(f"Sender: trying sending packet {ptype} to {ks} ")
                reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
                packet_data = { 'version' : 1, 
                    'source' : {'ID' : me, 'address' : config['qks']['ip'], 'port' :  config['qks']['port']},
                    'routing' : {'address' : config['routing']['ip'], 'port' :  config['routing']['port']}, 
                    'timestamp' : ptime,
                    'type' : ptype,
                    'auth' : "",
                    'hop' : 0,
                    'forwarder' : me
                    }
                if ptype == 'S': 
                    ids = graph.get_node(me).get_saes()
                    packet_neighbors = [{'ID' : id} for id in ids]
                    packet_data['neighbors'] = packet_neighbors
                    packet = lsaPacket(packet_data)
                elif ptype == 'K': 
                    ids = list(neighbors)
                    costs = list(d.values())
                    packet_neighbors = [{'ID' : id, 'cost': cost } for id, cost in zip(ids, costs)]
                    packet_data['neighbors'] = packet_neighbors
                    packet = lsaPacket(packet_data)

                p_enc = packet.encode()
                if (p_enc is not None):
                    size = packet.get_dimension()
                    writer.write(size.to_bytes(2, 'big'))
                    writer.write(p_enc)
                writer.close() 
                await writer.wait_closed()
                logger.info(f"Sender: sent packet {packet_data['type']} to {ks} ")
        except Exception as e: 
            logger.error(f"Exception in sendSocket: {e}")


async def forwardSocket(packet : lsaPacket, ip : str) : 

    global config , ksAddresses
    packet_srcID = packet.data['source']['ID']
    packet.data['hop'] += 1
    forwarder = packet.data['forwarder']
    packet.data['forwarder'] = config['qks']['id']
    res = True if (packet_srcID != config['qks']['id'] and ksTimestamps[packet_srcID][packet.data['type']] < packet.data['timestamp']) else False 
    if res: 
        for ks in list(ksAddresses.keys()) :
            addr = ksAddresses[ks]
            if ks in graph.get_node(config['qks']['id']).get_neighbors().keys() and forwarder != ks:
                logger.info(f"Forwarding: forwarding packet {packet.data['type']} from {packet.data['source']['ID']}  to {ks}")
                reader, writer = await asyncio.open_connection(addr['ip'], addr['port'])
                size = packet.get_dimension()
                writer.write(size.to_bytes(2, 'big'))
                writer.write(packet.encode())                  
                writer.close() 
                

async def updateRouting(mode : str = 'standard') -> bool : 
    removed = False 
    global graph
    threshold = time.time() - float(2*config['routing']['timer']) 
    removed = expireRoutes(threshold)
    await updateLinkCosts()

    if mode == 'force' or removed : 
        rts = graph.build_routing_tables(config['qks']['id'])
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
    up = False 

    ids = [ el['ID'] for el in neighbors]

    if ptype == 'S' and ksTimestamps[src][ptype] < timestamp : 
        up = True
        ksTimestamps[src][ptype] = timestamp
        old_saes = graph.get_node(src).get_saes() 
        for sae in ids: 
            if sae not in old_saes: 
                up = True
                graph.add_sae(sae, src)
                logger.info(f"UpdateGraph: added  sae {sae} ")
                

        for sae in old_saes: 
            if sae not in ids:
                up = True
                graph.remove_sae(sae)  
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
                    logger.info(f"UpdateGraph: removed link {ks}-{src} ")
    return up


async def lsaUpdate() : 
    global config , graph
    timer = config['routing']['timer']
    n = 0
    await asyncio.sleep(randint(0,timer))
    logger.warning(f"Timer: periodic update every {timer} s")
    while True: 
        await asyncio.sleep(timer)
        if n == 0: 
            await updateRouting('force')
        else: 
            await updateRouting()
        await sendSocket('K', time.time())
        await sendSocket('S', time.time())
        n += 1

        
async def listenForChanges() : 
    logger.info("    TIMER: LSA THREAD STARTED")
    global config, graph, cost_param
    timer = config['routing']['timer']
    me = config['qks']['id']
    await asyncio.sleep(timer*4)
    while(True): 
        await asyncio.sleep(randint(0,timer))
        logger.info("    TIMER: LSA THREAD STARTED")
        while True:
            rt = randint(0,timer) 
            await asyncio.sleep(rt)
            await random_update(me) 
            await updateRouting(mode='force')
            await asyncio.sleep(timer-rt)

async def random_update(me): 
    r_act = randint(0, 3)

    if r_act == 0: 
        sae = f"s-{me}-{str(randint(0,10))}" 
        if  graph.add_sae(sae, me) is not None:
            await sendSocket('S', time.time())

    elif r_act == 1: 
        saes = graph.get_node(me).get_saes() 
        if (len(saes) > 1) :
            sae = saes[randint(0, len(saes)-1)]
            if graph.remove_sae(sae) : 
                await sendSocket('S', time.time())

    elif r_act == 2: 
        cost = randint(1,10)
        nodes = list(ksAddresses.keys() )
        dst = nodes[randint(0, len(nodes)-1)]
        if graph.add_link(me, dst, cost): 
            await sendSocket('K', time.time())

    elif r_act == 3: 
        links = list(graph.get_node(me).get_neighbors().keys()) 
        if (len(links) > 1) :
            dst = links[randint(0, len(links)-1)]
            if graph.remove_link(me, dst) : 
                await sendSocket('K', time.time()) 


async def initData() -> bool :
    # load server and SAE list from init file 
    global config, graph, http_client, cost_param
    
    graph.add_node(config['qks']['id'])
    for qks in config['neighbors']:  
        ksAddresses[qks['id']] = qks['routing_address']
        ksTimestamps[qks['id']] = { 'K' : 0.0, 'S' : 0.0}
        graph.add_node(qks['id'])
        graph.add_link(config['qks']['id'], qks['id'], cost_param['c0'])

    http_client = aiohttp.ClientSession()
    return True 


async def main() : 
    global config_file, config

    if len(sys.argv) == 2: 
        filename = sys.argv[1] 
    else: 
        filename =  "routing/config_files/test_conf0.yaml"
    config_file = open(filename, 'r')
    config = yaml.safe_load(config_file)
    config_file.close() 

    logger.info(f"starting ROUTING APP for server {config['qks']['id']}" )
    try : 
        res = await initData() 
        if not res: 
            logger.error("INIT ERROR: Wrong configuration") 
            return 
    except Exception as e:
        logger.error(f"INIT ERROR: Wrong configuration. EXCEPTION: {e}") 
        return 


    # running LSA thread
    lsaUpdateTask = asyncio.create_task(lsaUpdate())
    listenForChangesTask = asyncio.create_task(listenForChanges())
    logger.info(f"main : created tasks for timer and pubsub listener")

    try: 
        server = await asyncio.start_server(receiveSocket, '0.0.0.0', 7000)
        logger.info("Server created")
        async with server:
            await server.serve_forever()
    except: 
        logger.error("ERROR: unable to start server")
    finally: 
        lsaUpdateTask.cancel() 
        listenForChangesTask.cancel() 


if __name__ == "__main__":
    asyncio.run(main())

