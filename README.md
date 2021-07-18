# QKD key server 2.0

# TO BE UPDATED

## files and modules 
### qks_src 
This folder contains all files related with qks code. 
- routing folder contains routing files. 
    - lsaPacket : TCP packet class with encoding and decoding functionalities 
    - qkdGraph : graph structure class with support to QKS nodes and SAE nodes
- api : all function to be called when a request is received 
- server : main file to be executed with flask app inside
- vaultClient : interface module to intercat with vault 
- config_files folder contains config files and docker_compose 

## routing_test 
This folder contains old files related to routing algorithm development and timing results obtained during tests. 

## routing

## docs
This folder contains project APIs, DB and sequence diagram documentation as pictures and as plantUML code. 
QKDM docs can be found in qkdm repository 

## test.http 
simple file with some http requests for testing purposes 

# TODO 
* [x] indirect communication 
    * [x] routing process and routing algorithm 
    * [x] redis usage for routing tables and SAE info
    * [x] forwardData implementation 
    * [x] dinamic cost for routes -> routing talks to qkd modules
    * [x] indirect stream support 
* [ ] reserve key relaxed version (return reserved key list even if some are not reservable, not only a bool)
* [ ] managin secrets with Docker and not in clear in config files 
* [ ] implementing loggin with support to hypercorn (for multiprocessing) 
* [x] moving to asyncio and Quart, Hypercorn and Motor (replacing Flask, Gunicorn and PyMongo) to improve performances
* [ ] implement better timeout managment for http requests

