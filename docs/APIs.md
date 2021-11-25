# QUANTUM KEY SERVER APIs
## Northbound interface : SAEs/Admin to QKS

| method                | path  | action| note  | 
|-------                | ----  | ------| ----  |
| **getStatus**         | /api/v1/keys/*<slave_SAE_ID>*/status      | GET    |            |
| **getKey**            | /api/v1/keys/*<slave_SAE_ID>*/enc_keys    | POST   |            |
| **getKeyWithKeyIDs**  | /api/v1/keys/*<master_SAE_ID>*/dec_keys   | POST   |            |
| getPreferences        | /api/v1/preferences                       | GET    | admin only |
| setPreference         | /api/v1/preferences/*<preference>*        | PUT    | admin only |
| getQKDMs              | /api/v1/qkdms                             | GET    | admin only |
| registerSAE           | /api/v1/saes                              | POST   |            |
| unregisterSAE         | /api/v1/saes/*<SAE_ID>*                   | DELETE |            |
| startQKDMStream       | /api/v1/qkdms/*<qkdm_ID>*/streams         | POST   | admin only |
| deleteQKDMStreams     | /api/v1/qkdms/*<qkdm_ID>*/streams         | DELETE | admin only |
| registerQKS           | /api/v1/qks                               | POST   | admin only | 
| deleteIndirectStream  | /api/v1/qks/*<qks_ID>*/streams?force=     | DELETE | admin only | 

## External (QKS to QKS) interface 

| method                | path  | action| note  | 
|-------                | ----  | ------| ----  |
| reserveKeys           | /api/v1/keys/*<master_SAE_ID>*/reserve     | POST   |       |
| forwardData           | /api/v1/forward                            | POST   |       |
| create_stream         | /api/v1/streams                            | POST   |       |
| close_stream          | /api/v1/streams/*<key_stream_ID>*          | DELETE |       |
| exchangeIndirectKey   | /api/v1/streams/*<key_stream_ID>*/exchange | POST   |       | 

## Southbound interface :  QKD Module to QKS
| method                | path  | action| note  | 
|-------                | ----  | ------| ----  |
| registerQKDM          | /api/v1/qkdms             | POST      |       |
| unregisterQKDM        | /api/vi/qkdms/*<qkdm_ID>* | DELETE    |       |


## JSONs data
![](./img/API_server_JSON.png)

<!-- 
# Plant UML Codes 

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{   
    "**getStatus answer**" : "",
	"source_KME_ID": "String",
    "target_KME_ID": "String",
    "master_SAE_ID": "String",
    "slave_SAE_ID": "String",
    "key_size": "Integer",
    "stored_key_count": "Integer",
    "max_key_count": "Integer",
    "max_key_per_request": "Integer",
    "max_key_size": "Integer",
    "min_key_size": "Integer",
    "max_SAE_ID_count": "Integer"
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**getGey request**":"",
    "number": "Integer",
    "size": "Integer",
    "extension_mandatory": [
    {"require_direct": "Bool"},
    "..."
    ]
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**getGey answer**":"",
    "keys": [
    {
    "key_ID": "String",
    "key": "String"
    },
    "..."
    ],
    "key_container_extension" : {
        "direct_communication" : "Bool",
        "returned_keys" : "Integer"
    }
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**getGeyWithID request**":"",
    "key_IDs": [
    { "key_ID": "String (uuid4)" },
    "..."
    ]
}
@endjson

@startjson
{
    "**getGeyWithID answer**":"",
    "keys": [
    {
    "key_ID": "String (uuid4)",
    "key": "String"
    },
    "..."
    ]
}
@endjson


@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**getQKDM answer**":"",
    "QKDM_list" : [
        {   "QKDM_ID":"String", 
            "protocol": "String",
            "QKDM_IP" : "String",
            "destination_QKS" : "String" },
        "..."
    ]
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**registerQKDM request**":"",
    "QKDM_ID":"String",
    "QKDM_IP" : "String",
    "QKDM_port" : "Integer", 
    "protocol" : "String",
    "max_key_count" : "Integer", 
    "key_size" : "Integer",
    "destination_QKS" : "String"
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**registerQKDM answer**":"",
    "database_data" : {
        "host" : "String",
        "port" : "Integer", 
        "db_name" : "String",
        "username" : "String", 
        "password" : "String",
        "auth_src" : "String"
    },
    "vault_data" : {
        "host" : "String",
        "port" : "Integer",
        "secret_engine" : "String",
        "role_id" : "String",
        "secret_id" : "String"
    }
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**registerSAE request**":"",
    "id" : "String"
}
@endjson


@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**startQKDMStream request**":"",
    "destination_qks_ID" : "String" 
}
@endjson


@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**registerQKS request**":"",
    "QKS_ID" : "String",
    "QKD_IP" : "String", 
    "QKS_port" : "Integer", 
    "routing_IP" : "String", 
    "routing_port" : "Integer"

}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**reserveKeys request**":"",
    "key_stream_ID" : "String",
    "slave_SAE_ID" : "String", 
    "key_size" : "Integer",
    "key_ID_list" :     [ 
        { "AKID": "String (uuid4)",
            "kids" : ["String", "..." ]},
        "..."
    ]
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**createStream request**":"",
    "source_qks_ID" : "String",
    "key_stream_ID" : "String (uuid4)",
    "qkdm_id" : "String" 
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**closeStream request**":"",
    "source_qks_ID" : "String"
}
@endjson

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "**forwardData request**":"",
    "data" : "String",
    "decryption_key_ID" : "String",
    "decryption_key_stream" : "String",
    "iv" : "String", 
    "destination_sae" : "String"  
}
@endjson

@startjson 
{
    "**registerQKS request**": "", 
    "QKS_ID":"String",
    "QKS_IP" : "String",
    "QKS_port" : "Integer", 
    "routing_IP" : "String",
    "routing_port" : "Integer"
}
@endjson

-->