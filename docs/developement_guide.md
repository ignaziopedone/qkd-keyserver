This file contains detailed information about the developement of this project. 
You can find details about the APIs in the `/docs/APIs.md` file and a set of sequence diagrams for the interaction between the components in different scenarios in `/docs/sequence_diagrams.md`. 
For the deployment guide look at the `README.md` in the main folder of this repository. 

From the main folder all the components code and tests results are accessible. A detailed description of the repository files can be found at the bottom of the `README.md`. 

# Implementation details
The *QKS core* code can be found in the `qks_core` folder while the *routing module* code in the `routing` one. 
Both have been developed in Python 3.9 to take full advantage of the *async* patter and to exploit *type hints* improving code readability. 
All the developed Docker images are available on [DockerHub](https://hub.docker.com/r/ignaziopedone/qkd/), tags have been used to describe them. 

## QKS core 
The `qks_core` files have been packaged in a *Docker image* to simplify the deployment of the app. The Docker image can be built from the `Dockerfile` in the same folder as the code, with the command: 
``` docker build -f <path/to/dockerfile> -t <image_name:image_tag>```
Note that in a production environment the *Quart* web server should by run directly through the Python file, but an ASGI webserver (e.g. [Hypercorn](https://pgjones.gitlab.io/hypercorn/)) should be used in front of it. 
To run the server with Hypercorn use the command: 
``` hypercorn server:app ```
The Docker image should be modified accordingly.

### Interaction with other components
The interaction with MongoDB is performed through the official [motor](https://github.com/mongodb/motor) library, which provides support to asynchronous communication with the Python standard library `asyncio`. 
The asynchronous interaction with Redis is carried on with the [aioredis](https://github.com/aio-libs/aioredis-py) library; a version equal or higher to the `2.0.0` is required to correctly perform all the operations. 

The `asyncVaultClient` interface is built on top of the [async_hvac](https://github.com/Aloomaio/async-hvac) libraries used to interact with Vault. It contains all the methods required by the QKS and the QKDM, allowing to substitute Vault with another product without significant changes in the `api` code. It provides exceptions management and errors handling, returning empty values when the operation is not completed successfully. 

The interaction with Keycloak, to validate the authorization token received in the `Authorization` header of requests over the northbound interface is performed through the `verifyToken` token function which receives it and forward it to the Keycloak endpoint through the Keycloak REST API with the following call: 
```
  Method: POST 
  URL: http://<keycloak_host>:8080/auth/realms/<realm>/protocol/openid-connect/userinfo
  Headers: 
      - Content-Type: application/json
      - Authorization: Bearer <access_token>
```
When a request is received the server first checks if the sender is authenticated and then decode the received payload and check if all fields are present.
Detailed information on the available methods in the API can be found in the [official documentation](https://www.keycloak.org/docs-api/15.0/rest-api/).

The authentication is not bound to Keycloak or the OIDC protocol, therefore this function can be modified to support any other validation techniques, either online or offline. 

### Logging 
Loggin is performed with the standard Python library `logging`. The logger is configured before the Quart app initialization with the code: 
```logging.basicConfig(filename='qks.log', filemode='w', level=logging.INFO)``` 
and logs are perfomed executing the proper method on the `app.logger` object, for example for a *warning* message:  
```app.logger.warning(message_string)```
Data are both saved in the log file specified in the `basicConfig` method and printed on the standard output through the Hypercorn ASGI web server which runs with Quart. To save data persistently a persistent volume should be added to map the folder `/usr/app/qkd-keyserver/qks_core`

## Routing module
The `routing` files have been packaged in a *Docker image* to simplify the deployment of the app. The Docker image can be built from the `Dockerfile` in the same folder as the code, with the command: 
```docker build -f <path/to/dockerfile> -t <image_name:image_tag>```

### Cost function
The routing cost function can be found in the `/routing/asyncRoutingApp` file and computes the cost of each link in the following way: 
```
cost_param = {'c0' : 100, 'c1' : -50, 'c2' : -25}
def routeCost(old: int, new: int, tot : int) -> int  : 
	global cost_param
	delta : int = ( new - old ) 
	cost : float = cost_param['c0'] + cost_param['c1'] * ( new / tot ) + cost_param['c2'] * ( delta / tot ) 
	return int(cost)
```
It receives the number of available keys in the QKDM at the previous interaction `old`, the current number of available keys `new` and the maximum number of storable keys `tot`. `cost_parameter` is a global variable which contains the equation coefficients. 
This function can be updated and extended with other parameters without requiring any other change to the code. The only requirement is that the returned value must be greater than `0`, otherwise, it can cause unexpected behaviour in the Dijkstra algorithm. 

### Redis messages
The updates from the QKS are received from Redis `PubSub` topics, in the following way:
```
async def listenForChanges() : 
	pubsub : aioredis.PubSub = redis_client.pubsub()
	await pubsub.psubscribe(f"{config['redis']['topic']}-**")
	while True:
		message = await pubsub.get_message(ignore_subscribe_messages=True, timeout = 0.1)
		action, name = message['data'].split("-")
		# handle the message
```
Three topics are used: `<config_name>-sae` for information related to SAEs, `<config_name>-qks` for new QKSs added to the network from the northbound interface method and `<config_name>-link` for added or removed QKD streams. 
The topic name must be specified in the configuration file and must match between the QKS core and the routing module. 
The received message is a string formatted with `<action>-<name>` where action can be `add` or `remove` while `name` is the subject to which the action refers. 
Routing tables are produced by the *graph* object and are pushed into Redis executing a `pipeline` in the `updateGraph` function, which allows performing several actions in a single call, reducing the transmission overhead. 

### Routing packet parameters
The packet content can be updated and easily extended modifying the parameters list global variable in the `/routing/lsaPacket.py` file: 
```element_list = ["version", "type", "source", "routing", "neighbors", "timestamp", "auth", "forwarder"]```
The `encode` and `decode` functions of the JSON version does not require any update even if there are changes in the packet parameters, while the raw encoded version requires a code update to correctly handle changes. The size of each element in the raw encoded packet is defined in the `dims` dictionary global variable.  

### Logging
Loggin is performed with the standard Python library `logging`, and data are saved in the `/usr/app/qkd-keyserver/routing/routing.log` file, hence to persist logs a persistent volume should be added in the routing pod mapping the corresponding folder. 

# Kubernetes integration
The code of the operator can be found in the `/kubernetes/operator/operator.py` file. 
Thanks to the *kopf* framework all the modules, components and configuration required to interact with Kubernetes are automatically managed and the operator code is developed in a single file. 

There are three main functions related to action on resources in the operator: 
- `keyreq_on_create` is triggered when a `keyRequest` resource is created. It watches the parameters, perform the login for the `master_SAE` into Keycloak and then calls the `getKey` or `getKeyWithKeyIDs` on the QKS. If the requests is completed successfully it creates the corresponding secret. 
- `sae_on_create` is triggered when a `sae` resource is created. It perform login with QKS admin credentials into Keycloak and calls the `registerSAE` method to the QKS. If the parameter `registration_auto` is set to `true` it register the SAE into Keycloak. An error is returned if a user with the same username as the SAE is already present; to register a SAE already present in Keycloak the `registration_auto` parameter must be set to `false`
- `sae_on_delete` is triggered when a `sae` resource is deleted. It calls the `unregisterSAE` method to the QKS but does not delete the user from Keycloak. 

The operator does not perform any action when a `keyRequest` object is deleted. 
In the proposed solution it does not have the authorization to watch resource changes, therefore even if a keyRequest gets modified after its creation the operator will not react. This ensures consistency in secrets and avoids the risk of overwriting keys already returned. 

To create a function that will be triggered after action on a resource an annotation should be added on top of it specifying the group, the version and the name of the resource; e.g. for the `keyreq_on_create` function: 
```
@kopf.on.create('qks.controller', 'v1', 'keyrequests')
def keyreq_on_create(namespace, spec, body, name, **kwargs):
```

### Authorization management
The operator must have access to the custom resources `saes` and `keyRequests` to watch their creation, to `event` to discover when a new object has been created and to `secrets` to retrieve SAEs credentials and to save retrieved keys. 
A basic implementation of the operator cluster role is reported here: 
```
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: qkd-operator
rules:
- apiGroups: ["qks.controller"]
  resources: ["keyrequests"]
  verbs: ["*"]
- apiGroups: ["qks.controller"]
  resources: ["saes"]
  verbs: ["*"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["*"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["*"]
```

### Image building
The code can be packaged in a Docker image using the Dockerfile provided in the operator folder. 
The operator code must be run not as a standard Python file, but through the following command:
``` kopf run /path/to/the/operator.py ```
which allows the *kopf* framework to run the code required to interact with Kubernetes and to load all the needed libraries, embedding the provided Python code into a controller loop. 


