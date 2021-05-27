# DB model 

## MongoDB view 
![](./img/DB_model_JSON_server.png)
![](./img/DB_model_JSON_module.png)

## Routing model
![](img/RoutingTable_model_JSON.png)
![](img/qkdLSA_Packet.png)


# PlantUML JSON Codes

@startjson
#highlight "_id"
{
    "<color:blue>**quantum_key_server**" : "", 
    "_id": "String",
    "address" : {
      "ip" : "String", 
      "port" : "Integer"
    },
	"connected_sae" : [
		"String",
		"..."
	],
	"neighbor_qks" : [
		"String",
		"..."
	],
	"static_route" : "String"
}
@endjson

@startjson
#highlight "_id"
{
"<color:blue>**qkd_modules**" : "", 
  	"_id": "String (uuid4) ", 
	"address" : {
      "ip" : "String", 
      "port" : "Integer"
    },
	"reachable_qkdm" : "String",
	"reachable_qks" : "String", 
	"protocol" : "String", 
	"parameters" : {
		"max_key_count" : "Integer",
		"standard_key_size" : "Integer", 
		"parameter" : "anything"
	}
}
@endjson


@startjson
#highlight "_id"
{
"<color:blue>**key_streams**" : "", 
	"_id": "String (uuid4)",
	"dest_qks" : {
		"id": "String", 
		"address" : {
      "ip" : "String", 
      "port" : "Integer"
    }
	}, 
	"standard_key_size" : "Integer",
	"reserved_keys" : 
		[
			{ 
			"AKID" : "String (uuid4)",
			"sae" : "String",  
			"kids" : ["Integer", "..."] ,
			"key_length" : "Integer"
			} ,
			"..."
		],
	"qkdm" : {
		"id": "String (uuid4)", 
		"address" : {
      "ip" : "String", 
      "port" : "Integer"
    }
	}
}
@endjson


@startjson
#highlight "_id" 
{
"<color:green>**key_streams**" : "", 
  	"_id": "String (uuid4) ", 
	"available_keys" : ["String", "..."], 
	"source_id" : "String", 
	"dest_id" : "String", 
	"qos" : {
		"key_lenght" : "integer",
		"timeout" : "integer",
		"parameter" : "anything"
	}, 
	"status" : "String" 
}
@endjson

@startjson
#highlight "SAE ID" 
{
"<color:red>**Routing Table **" : "", 
  	"SAE ID" : "String", 
	"type " : "[static/dinamic]",
	"next hop id" : "String", 
	"next hop address" : {"ip" :"String", "port" : "Integer"},
	"cost" : "Integer" ,
	"length" : "Integer" 
}
@endjson



