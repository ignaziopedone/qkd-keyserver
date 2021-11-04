# QKD key server 2.0

## files and modules 
### qks_core
This folder contains all files related with qks code. 
- api : all function to be called when a request is received 
- server : main file to be executed with Quart app inside
- asyncVaultClient : interface module to interact with vault 
- vault_init : simple python script to initialize Vault 
- requirements.txt : pip requirements file  
- config_files folder contains config files for vault and redis and some example qks configuration 
- qksDockerfile : file to build docker image of the qks core module

## routing 
This folder contains routing module files. 
- asyncRoutingApp : async version of routingApp. It is the main file that offers routing functionalitie. 
- lsaPacket : packet class with encoding and decoding functionalities to/from JSON or to raw bytes
- qkdGraph : graph structure class with support to QKS nodes and SAEs
- requirements.txt : pip requirements file  
- config_files folder contains config files for some example routing configuration, matching qks configuration described above 
- routingDockerfile : file to build the docker image of the qks routing module

## tests 
This folder contains tests files: 
- docker-compose-test3.yaml : docker composed file used to deploy 3 QKS on a single machine. Note that only one redis, mongodb, vault and keycloak component are deployed
- global_test.http : simple file with some http requests for functionality testing purposes. Use this file with the configuration proposed in the docker-compose-test3.yaml 
- getKey_sppedTest : file that can execute multiple key requests in a sequential or parallel way retrieving their timings. If unchanged it works with the configuration proposed in docker-compose-test3.yaml 
- routing_test folder: old files related to routing algorithm development and timing results obtained during tests. This results are from an old version without async support, they are nomore up to date. They will be replaced in the future

## kubernetes 
This folder contains the files used for the deployment of the QKS stack in Kubernetes and the operator code. 
- resources folder : it contains all .yaml files required to deploy the QKS stack, both in terms of Deployments/StatefulSets and services. Each services can be found in the same file of its component. 
- config folder : it contains all ConfigMap, Secrets and persistent volumes required by the different components and from the operator
- operator folder : it contains all the file related to the operator development and deployment 
    - controller-deployment : yaml file for the controller deployment 
    - controller : python code that is executed by the controller
    - controllerDockerfile : file to build the docker image for the controller
    - KeyRequestCRD and SaeCRD : yaml files for the definition of custom resources controlled by the operator 
    - crd : folder with example of the defined CRDs

## docs
This folder contains project APIs, DB and sequence diagram documentation as pictures and as plantUML code. 
QKDM docs can be found in qkdm repository 

## other files 
- docker_compose.yaml : example of possible docker compose to deploy the QKS stack on a single node. Note that the QKDM require its peer to be initialized shortly after to start correctly



