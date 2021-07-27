# QKD key server 2.0

# TO BE UPDATED

## files and modules 
### qks_src 
This folder contains all files related with qks code. 
- api : all function to be called when a request is received 
- server : main file to be executed with flask app inside
- asyncVaultClient : interface module to intercat with vault 
- config_files folder contains config files for vault and redis and some example qks configuration 

## routing 
This folder contains routing algorithm files. 
- asyncRoutingApp : async version of routingApp. It is the main file that offers routing functionalitie. 
- lsaPacket : TCP packet class with encoding and decoding functionalities 
- qkdGraph : graph structure class with support to QKS nodes and SAE nodes
- config_files folder contains config files for some example routing configuration, matching qks configuration described above 

## routing_test 
This folder contains old files related to routing algorithm development and timing results obtained during tests. 
This results are from an old version without async support, they are nomore up to date. 
They will be replaced in the future


## docs
This folder contains project APIs, DB and sequence diagram documentation as pictures and as plantUML code. 
QKDM docs can be found in qkdm repository 

## other files 
- global_test.http : simple file with some http requests for testing purposes. Use this file with the configuration proposed in the docker_compose.yaml 
- docker_compose.yaml : example of possible docker compose with 3 qks and 4 qkdm. Note that only one redis server, one vault and one mongodb instance are used in this example, don't use this file to deploy in production. 
- requirements.txt : pip requirements file  

# TODO 
* [x] indirect communication 
    * [x] routing process and routing algorithm 
    * [x] indirect stream support 
* [ ] reserve key relaxed version (return reserved key list even if some are not reservable, not only a bool)
* [ ] managin secrets with Docker and not in clear in config files 
* [ ] implementing loggin with support to hypercorn (for multiprocessing) 
* [x] moving to asyncio and Quart, Hypercorn and Motor (replacing Flask, Gunicorn and PyMongo) to improve performances
* [ ] implement better timeout managment for http requests
* [ ] dockerfile with volumes for config files 

