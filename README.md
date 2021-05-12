# QKD key server 2.0

## files and modules 
### qks_src 
This folder contains all files related with qks code. 
- Routing folder contains routing files. 
    - lsaPacket : TCP packet encoding and decoding
    - qkdGraph : graph structure class 
- api : all function to be called when a request is received 
- server : main file to be executed with flask app inside