# qkd-keyserver

In order to start all docker containers needed for this implementation, open a terminal into this folder and run the commands:
```sh
docker-compose build
docker-compose up
```

## configuration

- register SAE ID and IP in db_init.sql before starting docker compose (they can also be registered later by directly accessing the mysql container)

- access keycloak panel with `admin` as user and `password` as password. Create a realm named `quantum_auth`.
- create a client and update information in client_secrets.json (client_id, client_secrets)
- create clients for each high level app
- post request to get the token. Example:
POST http://172.16.0.5:8080/auth/realms/quantum_auth/protocol/openid-connect/token
	HEADERS: Content-Type: application/x-www-form-urlencoded
	BODY: client_id=App1&client_secret=f9798a04-617b-4566-9ff3-d5a5377ae4ad&grant_type=client_credentials


## API
Note. keyServerIP can be 172.16.0.6 for alice key server or 172.16.0.7 for bob

```sh
GET https://keyServerIP/api/v1/keys/<slave_SAE_ID>/status
```
This method returns information about the number of available keys with the specified slave_SAE_ID

```sh
POST https://keyServerIP/api/v1/keys/<slave_SAE_ID>/enc_keys
```
This method retrieve one or more key that only the specified slave_SAE_ID can retrieve on its side. In the request it is possible to specify the number of keys to retrieve as well as the length of these keys with the following json content:
```sh
{'number' : number, 'size' : klen}
```

```sh
POST https://keyServerIP/api/v1/keys/<master_SAE_ID>/dec_keys
```
This method is used to retrieve keys that another SAE has already retrieved on its side. This side will forward one or more Key IDs that should be used inside this method to retrieve the same key(s).
Key IDs can be specified in body content with the following json object:
```sh
{'key_IDs' : [{'key_ID' : kid1}, {'key_ID' : kid2}, {'key_ID' : kid3}, ...]}
```


```sh
GET https://keyServerIP/api/v1/preferences
```
This method returns the current settings in the server

```sh
POST https://keyServerIP/api/v1/keys/preferences/<preference>
```
This method can be used to change one of the settings in the server. Possible values for <preference> parameter are: `timeout`, `log_level` and `qkd_protocol`.

```sh
POST https://keyServerIP/api/v1/keys/information/<info>
```
This method is used to retrieve information about the internal status of the server. Possible values for <info> parameter are: `qkd_devices` and `log`.

## troubleshoting
if Keycloak fails with this error code:

User with username 'admin' already added to '/opt/jboss/keycloak/standalone/configuration/keycloak-add-user.json'

deletes keycloak container and start docker compose again. This problem occurs when keycloak is stopped to quickly and it has no time to complete its configuration.

DB_VENDOR: H2 parameter let keycloak use an internal db. If it is no specified or another vendor is specified the references to a real db should be provided.
