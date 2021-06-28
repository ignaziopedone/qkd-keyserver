import qkdGraph
from lsaPacket import lsaPacket

from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from asyncio import run, Lock 
import sys
import time 
import yaml 

config_file = "config.yaml"
ksTimestamps = {}
ksAddresses = {}
graph = qkdGraph.Graph([])
redis_client = None 
mongo_client : MongoClient = None 
lock = {'K' : Lock(), 'S' : Lock(), 'R' : Lock()}
config : dict = {}


def next_power_of_2(x):  
    return 1 if x == 0 else 2**(x - 1).bit_length()

async def main(argv) : 
    global config_file

    config_file = open("qks_src/config_files/config.yaml", 'r')
    config : dict = yaml.safe_load(config_file)
    config_file.close() 

    me = config['qks']['id']
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
        run(main(sys.argv))

