# DB model 

## MongoDB view 
![](./img/DB_model_JSON_server.png)

## Routing packet
<img src="img/qkdLSA_Packet.png" width="600"/>

## Routing tables
<img src="img/RoutingTable_model_JSON.png" width="200"/>

<!-- ![](img/qkdLSA_Packet.png)
![](img/RoutingTable_model_JSON.png) -->

<!-- 
# PlantUML JSON Codes

@startjson
<style>
jsonDiagram {
  node {
	  BackGroundColor White
	}
}
</style>
{
    "<color:blue>**quantum_key_servers**" : "", 
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
"<color:blue>**qkd_modules**" : "", 
  	"_id": "String", 
	"address" : {
      "ip" : "String", 
      "port" : "Integer"
    },
	"reachable_qkdm" : "String",
	"reachable_qks" : "String", 
	"protocol" : "String", 
	"parameters" : {
		"max_key_count" : "Integer",
		"standard_key_size" : "Integer"
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
"<color:blue>**key_streams**" : "", 
	"_id": "String (uuid4)",
	"dest_qks" : {
		"id": "String", 
		"address" : {
      "ip" : "String", 
      "port" : "Integer"
    }
	}, 
		"qkdm" : {
		"id": "String (uuid4)", 
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
"<color:red>**Routing Table **" : "", 
  	"SAE ID" : "String", 
	"next hop" : "String", 
	"dest" : "String", 
	"cost" : "Integer" ,
	"length" : "Integer" 
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
    "version" : "Integer", 
    "type" : "String", 
    "source" : {
        "ID" : "String", 
        "address" : "String",
        "port" : "Integer"
    }, 
    "routing" : {
        "address" : "String", 
        "port" : "Integer"
    }, 
    "neighbors" : [
        {
            "ID" : "String",
            "cost" : "Integer"
        },
		"..."
    ],
    "timestamp" : "String",
	"authentication" : "String"

}
@endjson -->