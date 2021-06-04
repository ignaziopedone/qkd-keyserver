# QKD key server 2.0

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

## docs
This folder contains project APIs, DB and sequence diagram documentation as pictures and as plantUML code. 
QKDM docs can be found in qkdm repository 

## test.http 
simple file with some http requests for testing purposes 