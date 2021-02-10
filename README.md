# qkd-keyserver

This repository contains the code to run the full stack QKD implementation, composed by QKD Simulator, QKD Module and QKD Key Server. In order to simplify the code execution, a docker-compose file has been build. This allows to set up the whole environment with by using only the following command:
```sh
docker-compose up
```
However, before starting to use this code, some configuration needs to be done. Configuration regards the services needed to execute the code, e.g. `keycloak` (see [additional services](#additional-services) section) as well as specific settings in configuration file which must be selected before starting the execution (see [prerequisites](#prerequisites) section).


## additional services
This implementation lies on three external services which need to be properly configured:
- MySQL DB.

This service will run on a dedicated docker container. Its configuration can be found in `docker-compose.yaml` file as `mysql` service. Here it is possible setting the IP address of the service, the database and the password to be used. The settings also specify an initialization file that will be used to create the data structure and should be configured in order to initialize preliminar information on the key server. This file is `db_init.sql` in the root directory of this repository.

When a QKD Key Server runs, it must know the high level application (`SAE`) allowed to retrieve keys from it. It also must know the other QKD Key Server in the network to exchange keys with. This configuration can be automatized in further implementations. Right now this information must be manually provided before the QKD Key Server is sarted by modifying the related tables in `db_init.sql` file.

To add data related to registered SAE, modify `connectedSAE` table by adding the desired data at row 92 of `db_init` file. Here is already present an entry of a SAE with the related IP address. Actually IP address field is not currently used, hence it can be left unchanged. The first field is the ID of the registered SAE, it can be modified as desired and more entry can be added if required. Note that this ID will identify the SAE in the whole network, hence, if another SAE wants to exchange a key with the just registered one, it must provide the SAE ID you specify in this field.

For more information on how data are organized in the database, see [data model](#Data-model) section.

- Vault.

This service will run on a dedicated docker container. If you need to change basic configuration such as container's IP address or the mapping between the host port and the container one, modify `docker-compose.yaml` file. Vault service in this repository is already configured (its configuration is saved in the folders `volumes/alice-vault/logs`, `volumes/alice-vault/file` and `volumes/alice-vault/config`). If you want to use this configuration there is no need of performing any further step: vault keys are already configured in the related configuration files.

If you want to set up vault from scratch you can delete the content of the folders `volumes/alice-vault/file` and `volumes/alice-vault/logs` (`vault.json` file in `config` folder is mandatory, do not delete it) and start the container. Now the service can be reinitialized since the old configuration is lost. For information about how to configure vault service refer to the following guide:
https://blog.ruanbekker.com/blog/2019/05/06/setup-hashicorp-vault-server-on-docker-and-cli-guide/

Save the root token and the unsealing keys that will be issued during vault configuration as they will be required later.

- Keycloak.

This service will run on a dedicated container hence, as for the previous one, `docker-compose.yaml` file can be checked in order to modify basic configuration. Once the service is started you will need to register the clients allowed to access this service, in order to be able to retrieve authentication token that QKD Key Server will use to authenticate SAEs. You basically need to register a client for each SAE accessing the Key Server, as well as a client that represents the Key Server itself.

The first step to configure Keycloak is defining a `realm`. In order to do that, you need to access the web interface Keycloak server provides. This interface can be reached by opening a web browser and visiting the address `localhost:8080` after the container has started. Access the Keycloak admin console by using these credentials: `admin` as user and `password` as password (yes, the password is `password` but it can be changed in docker-compose if you want a serious one). Then press `Add Realm` button on the top left corner in order to create a new realm.

![](img/addRealm.png)

Note the chosen name of the realm as it will be required in configuration files later.

Now you can register clients. From the left menu, select `Client` entry to see the list of already registered clients. Add a new client by pressing the `Add Client` button on the right, you will be redirected to a form like the following:

![](img/addClient.png)

Select a client ID (it can be any name at your choice) and make sure client protocol is set to `openid-connect`), then press save and the client configuration page will appear. In this page it is important to select the right setup for the client. Note that all the clients (also the Key Server one) can be configured in the same way.
Please make sure each client has the following configuration:

__enabled__: `ON`
__client protocol__: `openid-connect`
__access type__: `confidential`
__Standard Flow Enabled__: `OFF`
__direct access grants enabled__: `ON`
__service accounts enabled__: `ON`
__browser flow__: `direct grant`
__direct grant flow__: `direct grant`

In `Advanced settings` section, it is possible to select the token lifespan, that basically is the time of validity of a token (it needs to be reissued after this time elapses). Feel free to select the timing you prefer in this field.

Please note that all the other fields that are not specified here can be left unchanged.

Press save to save the client configuration.

After pressing save button, scroll the page to the top. You can notice that a new tab named `credential` has appeared. If you are registering the client that represents your Key Server, select `credential` tab and copy the client secret field: you will need to use this data later for configuring the QKD Key Server.

Register as much clients as you need by repeating the above steps. You can always come back to this interface to register new clients when needed.

## prerequisites

This section refers to the configurations that need to be performed in configuration files before the execution of the QKD Key Server. This step should be performed after the [additional services](#additional-services) have been configured, hence you probably need to start docker containers with `docker-compose up` command once in order to set up the services, then stop all the containers and make the following configurations before launching again the whole execution with `docker-compose`.

The first file that needs attention is `config.yaml` file in `volumes/alice` directory of this repository. `internal_db`, `vault` and `keycloak` section must be configured with the correct data, depending by your configuration. Note that if you didn't reconfigure vault services, token and unseal keys are already set to the right value, otherwise you need to set the values obtained from your configuration. `settings` section regards the specific settings required by the standard for this key server: here it is possible to specify the maximum number of keys per request the server can return to a SAE, the server ID (`KME_ID`) and other parameters. `global` section refers to generic parameters in the server. In this section it is possible to specify:
- `qkd_protocol`: it is the preferred QKD protocol the lower level layers (QKD Module) should use. However it is not sure that the attached QKD Modules can implement this protocol, in this case the first available QKD Module will be used despite its protocol.
- `log_level`: this can be used to select the level of debug in the server. Allowed levels are `INFO` = 0, `WARNING` = 1 and `ERROR` = 2.
- `timeout`: it is the timeout parameter required by the standard, expressed in milliseconds. It should represent the time within the modules should exchange keys without quitting with an error.
- `tls`: this parameter can be used to enable https communication. Currently QKD Key Server communicate through http protocol, however, if you generate the required certificate and place client certificate in 
`volumes/source` folder and server certificate in `volumes/alice` folder you can enable tls communication by swhitching `enabled` parameter from `0` to `1`.

Once config file has been configured, it is needed to configure two more files before the server can be started. The first file is `unseal.sh` located in `volumes/alice`. Here it is needed to set vault address and unseal keys so that the storage can be correctly unlocked before the server starts. The second file that needs to be configured is `client_secrets.json` in `volumes/source`. Here it is needed to state the configuration for the client registered in keycloak service that will represent this Key Server. In this file it is important to change the following parameters as follow:
- `auth_uri`, `userinfo_uri`, `token_uri` and `token_introspection_uri` should be changed in two points: the address should match the keycloak IP address chosen in docker-compose file and, after _/realms/_ the name of the registered realms should be inserted. The remaining part of the URLs should be kept unchanged. As reference, `auth_uri` parameter should be modified as follow:
```
http://<Keycloak IP address and port>/auth/realms/<Realm name>/protocol/openid-connect/auth
```
- `client_id` and `client_secret` should match the ones retrieved during the registration phase of the client. They can be found in `credential` tab from the keycloak console. Please refer to [additional services](#additional-services) section for more information.

After these configurations are completed, Key Server can be started with the command:
```
docker-compose up
```

## API
The first three methods here stated, belong to [ETSI GS QKD 014](https://www.etsi.org/deliver/etsi_gs/QKD/001_099/014/01.01.01_60/gs_QKD014v010101p.pdf) standard (v1.1.1). Refer to this standard for detailed information about the parameters these function accept and return.

Note. All the replies to these methods are in JSON.

```sh
GET https://keyServerIP/api/v1/keys/<slave_SAE_ID>/status
```
This method returns information about the number of available keys with the specified slave_SAE_ID.

If the method returns the status code `200` the request went fine and all the information are available in the returned JSON object. If an error occurs the possible replies are:
- 400: Bad request. Server can reply this code if a request has an error (e.g. the destination SAE is not known in the network or no QKD link is established between the two Key Servers). Check the returned JSON object for details.
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.

```sh
POST https://keyServerIP/api/v1/keys/<slave_SAE_ID>/enc_keys
```
This method retrieve one or more key that only the specified slave_SAE_ID can retrieve on its side. In the request it is possible to specify the number of keys to retrieve as well as the length of these keys with the following json content:
```sh
{'number' : number, 'size' : klen}
```
If the method returns the status code `200` the request went fine and all the information are available in the returned JSON object. If an error occurs the possible replies are:
- 400: Bad request. Server can reply this code if a request has an error (e.g. the destination SAE is not known in the network, no QKD link is established between the two Key Servers, the number of requested keys is greather than maximum keys per request parameter selected in preferences, mandatory extensions or additional slave SAE are requested or more keys than available are requested). Check the returned JSON object for details.
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.


```sh
POST https://keyServerIP/api/v1/keys/<master_SAE_ID>/dec_keys
```
This method is used to retrieve keys that another SAE has already retrieved on its side. This side will forward one or more Key IDs that should be used inside this method to retrieve the same key(s).
Key IDs can be specified in body content with the following json object:
```sh
{'key_IDs' : [{'key_ID' : kid1}, {'key_ID' : kid2}, {'key_ID' : kid3}, ...]}
```
If the method returns the status code `200` the request went fine and all the information are available in the returned JSON object. If an error occurs the possible replies are:
- 400: Bad request. Server can reply this code if a request has an error (e.g. the destination SAE is not known in the network, key IDs are not specified in the format explained above or requested key IDs have not been reserved for the requesting SAE). Check the returned JSON object for details.
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.


```sh
GET https://keyServerIP/api/v1/preferences
```
This method returns the current settings in the server
If the method returns the status code `200` the request went fine and all the information are available in the returned JSON object. If an error occurs the possible replies are:
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.

```sh
POST https://keyServerIP/api/v1/keys/preferences/<preference>
```
This method can be used to change one of the settings in the server. Possible values for <preference> parameter are: `timeout`, `log_level` and `qkd_protocol`.
If the method returns the status code `200` the request went fine and the related preference is updated. If an error occurs the possible replies are:
- 400: Bad request. Server can reply this code if a request has an error (e.g. the parameters in the request are not allowed). Check the returned JSON object for details.
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.

```sh
POST https://keyServerIP/api/v1/keys/information/<info>
```
This method is used to retrieve information about the internal status of the server. Possible values for <info> parameter are: `qkd_devices` and `log`.
If the method returns the status code `200` the request went fine and all the information are available in the returned JSON object. If an error occurs the possible replies are:
- 400: Bad request. Server can reply this code if a request has an error (e.g. the parameters in the request are not allowed). Check the returned JSON object for details.
- 401: Unauthorized. This reply is issued if Keycloak token provided is invalid.
- 503: Generic server error.

## Key Server usage
Once started, you can start using QKD Key Server. Before requiring keys with SAEs, you still need to perform a further step: QKD Module registration.

Key Server starts without QKD Modules attached. However, docker-compose file starts a container with an instance of QKD Module, you can also start another instance of a QKD Module separately if you prefer. If this is the case refer to [QKD Module](https://github.com/ignaziopedone/qkd-module) repository's README.

If you want to use the QKD Module already provided with this docker-compose file, you just need to complete the registration phase. In order to do that, you need to make a POST request to the module, by indicating the IP address of the server to register against. An example request is the following:
```
import requests
 x = requests.post('http://<Module IP and Port>/attach_to_server', data=repr('<Key Server IP and Port>'))
```
Note that Key Server IP is a string.

Once all the involved Key Servers have a module registered on it, they start to exchanging keys and keys can now be retrieved from SAEs.

SAE must possess an authentication token in order to talk to Key Server. Authentication token must be retrieved from Keycloak service. It is therefore mandatory to register a client on Keycloak for any SAE willing to reach the Key Server and use the clientID and secret that comes out the registration phase to request a token. See [additional services](#additional-services) section for information about how to register a client in Keycloak.

After the client has been registered, a token can be retrieved with a POST request to Keycloak service. An example of request in python is the following:
```
import requests

x = requests.post('http://<Keycloak IP and Port>/auth/realms/<Realm Name>/protocol/openid-connect/token', data='client_id=App1&client_secret=69aa0a3a-09a7-49f8-9364-c171b12b74b9&grant_type=client_credentials', headers={'Content-Type': 'application/x-www-form-urlencoded'})
```
Note that `Content-Type` header is mandatory and Keycloak IP must be the same registered in `volumes/source/client_secrets.json` (you'd better use the network IP registered in docker-compose file instead of accessing Keycloak with the host address, since a mismatch on IP addresses in this phase will result in an invalid token). Also make sure to replace `client_id` and `client_secret` in the request body with the data you obtained from the client registration.

If the request is fine, the result of the token request is a JSON object containing the token and some additional metadata (e.g the expiration time of the token). Copy the token and use it in all the request made to the Key Server. The token must be provided in a dedicated header named `Authorization` and the content of this header should be `Bearer` followed by the token. As reference, an example request for the `status` method is here reported:

```
x = requests.get('http://10.0.2.15:6000/api/v1/keys/SAE11223344/status', headers={'Authorization':'Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJEZFYxM3ZrZUprbUhFTUl6bmJldUtCd2pjMXVCN0NqSkZCQXZsTlE4QkY4In0.eyJleHAiOjE2MTIwNDk3MjIsImlhdCI6MTYxMjAxMzcyNSwianRpIjoiOTM0OTkyZmMtNGU4Yy00NjYzLTkxZDYtZTJlYzIxMjQ0ZGJjIiwiaXNzIjoiaHR0cDovLzEwLjAuMi4xNTo4MDgxL2F1dGgvcmVhbG1zL3F1YW50dW1fYXV0aCIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiIwYTA5MjQyZi04OGE2LTQ0ZDEtYWI2My02YjE3MGE0MWVmNWQiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJBcHAxIiwic2Vzc2lvbl9zdGF0ZSI6IjRhOTYyN2U4LTAyYjktNDU0OS05Yzc4LTdjYmNjNjEyNjI1NCIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdfSwicmVzb3VyY2VfYWNjZXNzIjp7ImFjY291bnQiOnsicm9sZXMiOlsibWFuYWdlLWFjY291bnQiLCJtYW5hZ2UtYWNjb3VudC1saW5rcyIsInZpZXctcHJvZmlsZSJdfX0sInNjb3BlIjoiZW1haWwgcHJvZmlsZSIsImNsaWVudElkIjoiQXBwMSIsImNsaWVudEhvc3QiOiIxMC4wLjIuMTUiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInByZWZlcnJlZF91c2VybmFtZSI6InNlcnZpY2UtYWNjb3VudC1hcHAxIiwiY2xpZW50QWRkcmVzcyI6IjEwLjAuMi4xNSJ9.md6zvHs82znozahXJBvOl3096B-y1Y0bQpv7RfhJwO6K65xODm2WzJW1KevfpV9xDXGa-zUo8tfd0WYAbGLV9n4t3JqQHuADSaGg7iky_Z5FvnvLGiyrvmwcQEcBF05JvdgNvzRmdcQDDcezjk7tifrb397-Nlb0zIka8kULVqc0vG3oGepmuZTAyOjN_yBmwuoj0Ue-MQsrzFMr161G-irOhcG15DzMCCI9J3XHcJpFu0jHHji9QNYlA5y8qFnHvlSctKCT1Ru1PsvzY-tRZt0CcT64Vd2nbYecahG0nLHNg2alAIplzB4zw8YeW1mwKfOW_HsJflOHmOlw'})
```

In this repository it is also present a dummy implementation of a SAE that can perform all the above API requests. This implementation can be used as further reference to get details on the interaction between the SAEs and the Key Server. The implementation is located in `SAEtest.py` file in this repository. You can lauch this file by appending the authentication token as command line parameter and then use the CLI interface to make calls to the Key Server on a SAE behalf. If you want to use this test script, remember to modify the SAE ID and the Key Server IP address at row 7 and 8 of the file, in order to match your configuration.

## Workflow
When docker-compose starts, two scripts are launched: unseal.sh will unlock vault storage, then cleanDB.py file will reset the default configuration on vault and mysql DB in order to start from a clean condition. Then QKD Key Server is started.

When started, Key Server launches its web interface with Flask and a thread that will be in charge of manage the attached QKD Modules. The thread will fetch the list of destination (the list of other Key Servers in the network to exchange keys with) from the table `exchangedKeys` in the mysql DB, for each destination, it select one QKD Module (if available) and try to establish a connection by calling `OPEN_CONNECT` method from QKD Module. If OPEN_CONNECT is successful, the involved QKD Module will start to exchange keys until their maximum allowed is reached. At this point the SAEs can retrieve keys from the involved QKD Key Servers.

Let's now analyze the workflow for the three API belonging to the ETSI standard.

When `status` method is called, it should return a set of information about the keys available with the SAE destination specified. Key server must only retain information about the SAEs connected to it, when one of its SAE request information for an unknown SAE, the Key Server starts a discovery procedure by asking all other Key Servers if they have a SAE attached with the specified SAE ID. At the end of discovery procedure an error is returned if none of the other Key Servers know the destination. If the destination Key Server is found, `exchangedKeys` table from DB is queried, by using the Key Sever ID (KME_ID) as key. In this table are stored the most of the data `status` method should return. From `KmeExchangerData` table, by using the KME_ID, the ID of the QKD Module that is used to exchange the keys with the destination key server is retrieved. This information is used to query the QKD Module about the number of currently available keys. Note that status method should also return the ID of the calling SAE. In a first implementation a relation between the SAE ID and its IP was implemented, however, SAE acts as a client, hence its IP can be different among different calls. It is not possible to retrieve the SAE ID from its IP, hence right now, the IP of the calling SAE is returned instead of its ID. A further improvement can consists in sending the SAE ID within the request body, even if it is not foreseen by the standard.

When `enc_keys` method is called from a SAE to retrieve one or more keys. In the request must be specified the target SAE. This information will be used to understand the target Key Server the keys should be exchanged to. Information about the target Key Server as well as the QKD Module in charge of exchanging keys are retrieved in the same way as done for the `status` method. Once this information are retrieved, the key server checks if the request is fine by checking the request parameters (e.g. if the number of requested keys is lower than or equal to the maximum key per request, if enough keys are currently available and so on). If all the checks are fine, the server requests the required keys to its QKD Module. Once the keys are retrieved, it assign a key ID to them and forward the key ID to the target Key server so that it can retrieve the same keys and store them in the vault storage. During this phase the target key server will save this key ID in `reservedKeys` table, to make sure that keys will be returned only to the requested target SAE. Besides, retrieve the keys from the QKD Module in this phase, ensures that those keys will not be used for other SAEs since they are already taken from the module. If reservation phase is fine, Key Server returns the keys together their IDs to the calling SAE and the method returns.

> Note: Key IDs are calculated using uuid4. However, QKD Module already has an ID to uniquely identify the key stream (keys are retrieved from the module by specifying this stream ID and the index of the key in the stream). It is possible to modify this implementation in order to forward the module stream ID and the index instead of generating new key IDs on the fly.

When `dec_keys` method is called the calling SAE must specify one or more key IDs regarding keys already retrieved from the companinon SAE. The function will check that requested key IDs are reserved for this SAE by checking `reservedKeys` table and if all checks are fine, it returns the requested keys.

## Data model
Data inside database are organized in different tables. All the details can be seen in `db_init.sql` file. The currently available tables can be depicted from the following figure:

![](img/db_norel.png)

These tables came out from different modification to the implementation, hence a review of the tables is suggested in order to delete redundant entries and unused tables.

In particular, `currentExchange` and `completedExchanges` tables should belong to a previous implementation and should be removed safely. `bb` and `handles` tables regards QKD Module and its simulator. They should be created from the module itself and detached from the Key Server since each module should have its own table. Moreover, `connectedSAE` tables saves a reference of the SAE IP besides its ID. As previously said, SAE IP can change since SAE is a client for the Key Server, hence there is no need to store this data.

A cleaner situation of the data model used by the QKD Key Server is the following:

![](img/db_clean.png)


## Troubleshoting
if Keycloak fails with this error code:

User with username 'admin' already added to '/opt/jboss/keycloak/standalone/configuration/keycloak-add-user.json'

deletes keycloak container and start docker compose again. This problem occurs when keycloak is stopped to quickly and it has no time to complete its configuration.

DB_VENDOR: H2 parameter let keycloak use an internal db. If it is no specified or another vendor is specified the references to a real db should be provided.

## Future works
The implementation in this repository is a working version of a QKD Key Server. Due to the entity of this first implementation, some improvements were left to further works.

- Right now, any client can access to all the REST API described before. However it can be useful to split the API in two different sets. The standard ones (`status`, `enc_keys` and `dec_keys`) can be accessed by any kind of client. The other API should instead be accessed by some _administration_ clients that can use those methods to modify server settings. In this way server settings access is restricted only to certain kind of clients.

- Right now, as soon as a QKD Module is attached, the server try starting a key stream exchange by calling OPEN_CONNECT method with all the valid destinations it found in its list. In a real scenario, a QKD link must be manually set up between two destinations, hence it is better to remove the automatic start of the key exchange and define an API to manually start the exchange.

- Right now, the list of QKD Key Servers available in the network must be manually update in the DB itself (by editing `exchangedKeys` table in `db_init.sql` file). An API can be proposed to register new QKD Key Servers in the network in order to simplify this procedure.
