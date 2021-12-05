This files contains the deployment guide for the entire project and the description of the files and folders in this repository. 
For a more in-depth details about the implementation choices read the file `docs/developement_guide.md`. 
For information about the APIs read the file `docs/APIs.md`

# Deployment guide 
This section explains all the steps required to deploy the entire QKS stack presented in this repository and in the QKDM one into a Kubernetes cluster. The first section describes how to deploy the stack, while the second shows how to integrate it with the operator. For each step a correctly deployed [K3s](https://k3s.io/) cluster is considered running on the used machine; refers to K3s official documentation to find out how to install it. 
Because the QKS can run on its own and is not bound to Kubernetes, the last section describes how to deploy the entire stack on Docker

## Deployment in Kubernetes 
To deploy the stack on the K3s cluster a set of configuration files are required: an example set can be found in this repository in the `kubernetes` folder. All the paths shown in this section refer to this repository in the textiasync branch. First of all a namespace in which the entire stack will be deployed must be choosen. To create a new namespace use the command:	
```kubectl create namespace <namespace_name>```
To create any resource described in this chapter create the corresponding `.yaml` file and use the command:
```kubectl apply -n <namespace_name> -f <path/to/the/file>```
To deploy the stack you must first create the resources related to MongoDB, Vault, Redis and Keycloak and after that the QKS core and the routing module. Persistent volume resources are required both for Vault and for MongoDB and are the only resources that are not namespace scoped. You have to create them assigning a size compatible with the size of the network you are going to have. For a 3 nodes network with the parameters used in the example files,  100 Mbit for each one was enough. An example file can be found in `kubernetes/config/persistent_volume.yaml`

### MongoDB
To deploy *MongoDB* create, in the corresponding namespace, a secret with two keys: 
`mongo-root-username` and `mongo-root-password` with the admin credential required by the QKS to access the database and to create users and databases for the QKDMs. Data in Kubernetes secret must be encoded in the `base64` format. An example file can be found in `kubernetes/config/mongo_secret.yaml`
Now you have to create the mongoDB `statefulSet`, the corresponding `service` and the `persistentVolumeClaim` applying the resources in `kubernetes/resources/mongo.yaml`. 
Because MongoDB database and collections are created only after the first object insertion and objects do not have a fixed structure it is not required to provide an initialization script. 
 

### Redis
To deploy Redis create in the namespace a `configMap` with the configuration file that should be injected in the Redis container. Refer to the example file in `kubernetes/config/redis_configmap.yaml` to enable authenticated access and change the `password` at line 8. 
Redis `deployment` and `service` can be created applying the file in `kubernetes/resources/redis.yaml`.
The topics to be used for messages and the database for routing tables are defined in the QKS core and routing configuration file.

### Keycloak
Keycloak configuration requires both a `configMap` and a `secret` resources. 
The former should contains the JSON representation of the *realm* that will be used: it must contains the *client* object for the QKS and the roles for *admins*, *saes* and *QKDMs* as well as the mapping for the data returned in the login token. The JSON object can be exported from an already running instance and can be copied in the `configMap`. The `secret` object should contain admin credentials both for the QKS admin user and for the Realm admin, the QKS client ID and its secret (that should match the ones in the configMap). 
Keycloak deployment and service configurations can be found in `kubernetes/resources/keycloak.yaml`. The `nodePort` service type is not mandatory and it can be converted into a `clusterIP` type if access from the outside is not necessary. 

To retrieve the authentication token a user should interact with Keycloak with the following HTTP call: 
```
Method: POST 
URL: http://<keycloak_host>:8080
	/auth/realms/<realm>/protocol/openid-connect/token
Headers: Content-Type: application/x-www-form-urlencoded
Data:   client_id=<client_id>&client_secret=<client_secret>&
	grant_type=password&scope=openid&username=<username>&password=<password>
```

If the login procedure is completed successfully the access token will be placed in the `access_token` field of the returned JSON object.
With the proposed configuration the `realm` to be used is *qks* and the `client_id` is *qks*, but they can be changed in the configuration file. 
The token must be sent to the QKS in the *Authorization* header: 
```Authorization : Bearer <token> ```


### Vault
The Vault container requires a configuration file to be injected to correctly set up the server. An example configMap which contain this file can be found in `kubernetes/config/vault_configmap.yaml` 
Deploy the Vault `statefulSet` and `service` through the file `kubernetes/resources/vault.yaml`
Vault requires both inizialization and unsealing procedure before being accessed by the QKS. Initialize it executing the following command: 
```kubectl exec -n <namespace_name> --stdin --tty <vault_pod_name> -- vault operator init```
and unseal it with: 
```kubectl exec -n <namespace_name> --stdin --tty <vault_pod_name> -- vault operator unseal ```
Use the parameters `--key-shares` and `--key-threshold` in the `init` command to specify the total amount of unsealing keys and how many of them are required to unseal the system after a reboot. Save the returned `root token` that must be injected in the QKS core configuration. 

### QKS core
The QKS core requires a configuration file containing the information on how to reach and access all the other external modules. The `.yaml` file can be injected in the container through a `configMap` as for the other components. 
The `root token` returned during the Vault initialization phase has to be placed in this configuration file as well as MongoDB and Redis credentials. A complete configuration example can be found in `kubernetes/config/qks_configmap.yaml`
The deployment object and the corresponding service can be created applying the file `/resources/qks.yaml`. The NodePort used to expose the service can be changed to any other unused port or a `LoadBalancer` service type if needed. 
A section of the configuration file with some details on the filed is reported here:
```
data:
  qks-config: |
    qks:
      id: qks1
      ip: qks-service       		# service name to reach the core from the cluster
      port: 4000            		# service port to reach the core from the cluster
      max_key_per_request: 20   
      max_key_size: 512
      min_key_size: 128
      max_sae_id_count: 0
      indirect_max_key_count: 20 	# total numbers of keys that can be reserved for indirect requests
    mongo_db:
      host: mongodb-service 		# MongoDB service name
      port: 27017					# port of mongoDB service
      user: rootuser
      password: rootpwd
      auth_src : admin      		# database used for authentication
      db : qks              		# database to use for storing data
    vault: 
      host : vault-service  		# Vault service name
      port : 8200					# port of Vault service
      token : s.KxoGNMbCu5Yvu7das	# root token  
```

### QKS routing
As for the core component also the routing ones require a configuration file that can be injected in the container through a `configMap`. In the `qks` and `routing` parameters it must contain the information on how to reach the core and the routing module from the outside of the cluster, which are the information that will be spread by the routing algorithm: the ports must correspond to the ones exposed through the `NodePort` services and the address must be public ones. The `redis` and `mongo_db` parameters should match the ones in the QKS core module configMap. 
The module can be deployed through the resources in `kubernetes/resources/routing.yaml`. As for the core module also the routing service can be changed to a `LoadBalancer` type if needed. 
A section of the configuration file with some details on the filed is reported here:

```
data:
  routing-config: |
    qks:
      id: qks1  
      ip: core.qks1.cluster1    # cluster address
      port: 30000               # node port
    routing: 
      timer : 20
      ip: routing.qks1.cluster1 # cluster address
      port : 30500              # node port
```

### QKDM
The QKDM is the last component that should be deployed in the stack. Because it requires a registration procedure its deployment is not as straightforward as for the other ones. 
If the other peer the module is connected to is attached to a QKS which is not known in the current QKS it must be registered with the corresponding API (`POST /api/v1/qks`). Because Keycloak in the proposed configuration does not consider valid for interacting with the QKS tokens requested by users outside of the cluster network a pod containing management script has been developed and its resource file can be found in `kubernetes/QKDMmanagement/management-pod.yaml`. 
To register the new QKS through the pod script execute it with the argument `3` followed by the QKS data (an example can be found in the pod file). You will need an account with the `admin` role on the QKS client to perform this operation and all the other management operations: you can register it through the Keycloak admin console or this pod script (with the argument `1`)
The QKDM can be registered to the QKS either through its API (`POST /api/v1/qkdm/actions/attach`) or by an admin interacting directly with the QKS. The second option is preferred because it allows you to save returned information in a configMap; otherwise a persistent volume is required to safely store those data even in case of crashes because the QKDM pod can not modify configMap objects. 
To register it with the script launch the pod with argument `2` followed by the QKDM data; returned data will be printed on the standard output and can be copied in the QKDM configMap (an example can be found in `/config/qkdm_configmap.yaml`)
The QKDM example pod, which uses the *fakeKE* protocol, will fail if it controls the *sender* device and if the other peer is not already up: instantiate first the *receiver* device and then the sender. Pay attention to the fact that the *sender* in the `device` configuration parameter must contain the information on how to reach the receiver in the other node, while the latter must specify the `containerPort` it is listening on. 
An example of the `deployment` and `service` resource can be found in `kubernetes/resources/qkdm.yaml`.
A QKDM stream can be started by an administrator directly through the corresponding API to the QKS (`POST /api/v1/qkdms/<qkdm_id>/streams`) or with the script in the management pod (with argument `4`)
A section of the configuration file with some details on the filed is reported here:
```
data:
  qkdm-config: |
    qkdm:
      id: qkdm1                     # ID of this module
      dest_ID: qkdm2                # ID of the peer module
      dest_IP: qkdm.qks2.cluster2   # address of the peer module 
      dest_port: 31000              # nodePort of the peer module
      ip: qkdm-service              # service name to reach the QKDM from the cluster
      port: 5000                    # service port to reach the QKDM from the cluster
      key_size: 128
      max_key_count: 100
      protocol: fake                # name of the used QKD protocol
      init: true					# set to true to use the initialization data in the file
    qkd_device:
      role: sender                  # role of the device 
      host: device.qks2.cluster2    # address of the peer device  
      port: 32000                   # nodePort of the peer device 
```

## Kubernetes Operator integration
The operator can be deployed in the Kubernetes cluster to provide an easier interaction with the QKS from the SAEs point of view, but it is not mandatory: the QKS stack is completely functional also on its own but requires interaction through its REST interface. 
The files required to deploy the QKD operator in the cluster are located in the `kubernetes/operator` folder. 
The `saes` and the `keyRequests` custom resources can be created applying the `kubernetes/operator/saeCRD.yaml` and `kubernetes/operator/keyRequestCRD.yaml` files, they do not require the namespace parameter in the command because resource definition is valid for the entire cluster even if the resources are namespace scoped. 
In an environment where Role-Based Access Control (RBAC) has been enabled the operator must be granted access to the resources it has to manage with cluster-wide permission because SAEs should operate in a different namespace from the operator. 
Apply the `clusterRole`, the `clusterRoleBinding` and the `serviceAccount` describe in `kubernetes/operator/operatorRBAC.yaml` changing the clusterRole `subjects:namespace` parameter with the namespace the stack is running in. 
The operator can be deployed as a standard deployment object, which template can be found in `kubernetes/operator/operator-deployment.yaml`. It is necessary to specify in the deployment object the name of the namespaces where the operator can find the secret in used to access keycloak with admin role to create new SAEs users in the `SECRET_NAMESPACE` environment variable as shown in the code reported here below:
```
spec:
    serviceAccountName: qkd-operator
    containers:
    - name: qkd-operator
        image: ignaziopedone/qkd:qks_operator
        env: 
        - name: SECRET_NAMESPACE 
        value: qkdns		# name of the namespace where master secrets and credentials are located
```

Once the operator is deployed, SAEs can be registered creating a `sae` resource specifying the name and `true` in the `registration_auto` parameter. 
With the SAE correctly registered, its Keycloak credentials can be accessed by administrators in the secret `<sae_name>-credentials` in the namespace it is deployed into.
An example of a `sae` object is reported here: 
```
apiVersion: "qks.controller/v1"
kind: Sae
metadata:
  name: saeA01
spec:
  id: sae_A01 
  registration_auto: true 
```
To retrieve a key create a `keyRequest` object specifying the master and the slave SAEs and the key requested. To retrieve keys already reserved insert their IDs in the `ids` parameter. If the request is completed successfully a secret with the same name as the keyRequests will be created in the SAE namespace, in case of failure nothing will be created and the requests should be recreated; no *retry* behaviours have been implemented. 
Because resource names in Kubernetes have to be unique in a namespace each SAE should identify a way to produce unique names such as UUIDs. 
An example of a `keyRequest` object is reported here: 
```
apiVersion: "qks.controller/v1"
kind: KeyRequest
metadata:
  name: requestA
spec:
  number: 1
  size: 128
  master_SAE_ID: sae_A01 
  slave_SAE_ID: sae_B02
```

## QKS deployment in Docker
This section describes how to deploy the entire QKS stack in Docker. 
The same configuration files described in the Kubernetes section are required with Docker, despite they are not deployed through configMaps and secrets. Example files can be found in the `qks_core/config_files` and in the `routing/config_files` folder for the QKS, and in its [repository](https://github.com/ignaziopedone/qkd-module/tree/async) for the QKDM in the async branch. 
For each pod that requires a configuration file injected through a configMap, the configuration file should be injected through a volume in the same path as the configMap. Environment variables injected through secrets here must be passed directly as variables in the container arguments or through Docker secrets. There are no differences in the parameters of the configuration files between the two deployment scenarios. 
To simplify the deployment a *docker-compose* file can be used, but it does not solve the issues related to the injection of configuration data and the required deployment sequence described in the Kubernetes section. 
If a docker-compose is used each container can reach the others via their container name, the mapping between the name and the IP address is performed directly by Docker when the container is created through Docker networking functionalities, while services must be replaced with the corresponding port mapping.  
An example docker-compose file can be found in the GitHub repository.



# Files and modules 
## qks_core
This folder contains all files related with qks code.
- server : is the file that contains the Quart server which receives and manages the incoming HTTP calls, return formatted results and handles error messages. It can receive in the input parameters the name of the configuration file to use. 
- api : contains all the functions called from the `server`, it contains the main application logic of the three interfaces and the management functions required to init the server.   
- asyncVaultClient : is an asynchronous interface built to communicate with Vault which contains all the methods required by the QKDM and the QKS to interact with Vault.
- vault_init : simple python script to initialize and unseal Vault 
- requirements.txt : pip requirements file for the QKS core module
- config_files folder: contains config files for vault and redis and some example qks configuration for the Docker deployment 
- qksDockerfile : Dockerfile to build docker image of the qks core module

## routing 
This folder contains routing module files. 
- asyncRoutingApp : is the file with the routing algorithm, that manages all the routing logic, the interaction with Redis and the computation of the cost for each link. It can receive in the input parameters the name of the configuration file to use.
- lsaPacket : contains the packet class, both in JSON and in the raw encoded version and the functions to encode and decode them.
- qkdGraph : contains the graph class and the classes for nodes and SAEs. It is used to represent the QKD network and the links between QKSs and to compute and return routing tables. 
- requirements.txt : pip requirements file  
- config_files folder contains config files for some example routing configuration, matching qks configuration described above 
- routingDockerfile : dockerfile to build the docker image of the qks routing module

## tests 
This folder contains tests files: 
- docker-compose-test3.yaml : docker composed file used to deploy 3 QKS on a single machine. Note that only one redis, mongodb, vault and keycloak component are deployed
- global_test.http : simple file with some http requests for functionality testing purposes. Use this file with the configuration proposed in the docker-compose-test3.yaml 
- getKey_speedTest : file that can execute multiple key requests in a sequential or parallel way retrieving their timings. If unchanged it works with the configuration proposed in docker-compose-test3.yaml 
- routing folder: files related to routing algorithm testing and timing results obtained during tests. Look at .xlsx file to see formatted results 
- getKey_tests: files related to QKS testing and timing results obtained during tests. Test have been performed with 2 o 3 nodes in the netwkork. Look at .xlsx file to see formatted results 
- fakeKE_key_rate: files related to the QKDM testing, the reached speed and the success rate of requests with limited exchange rate. 

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



