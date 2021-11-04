## QKD Key Exchange (PTP) 

@startuml
skinparam sequenceMessageAlign center
actor "Alice's SAE" as ASAE order 2 #lightCoral
actor "Bob's SAE" as BSAE order 7 #lightCoral
participant "Alice's QKS" as AQKS order 3 #LightBlue
participant "Bob's QKS" as BQKS order 6 #LightBlue
participant "Alice's QKDM" as AQM order 4 #LightGreen
participant "Bob's QKDM" as BQM order 5 #LightGreen

== a) QKD module registration ==
autonumber 1.1
 [-[#green]> AQM ++ #LightGreen:**from admin:**\n attach_to_server( {server info} ) 
AQM -[#blue]> AQKS ++ #LightBlue: registerQKDM \n( {module info} )
AQKS -[#blue]-> AQM --: < environment data \n for QKDM >
deactivate AQM
BQM <[#green]-] ++ #Lightgreen: **from admin:**\n attach_to_server( {server info} )
BQM -[#blue]> BQKS ++ #LightBlue: registerQKDM \n( {module info} )
BQKS -[#blue]-> BQM --:  < environment data \nfor QKDM >
deactivate BQM

== b) Key stream creation == 
autonumber inc A

[-[#blue]> AQKS ++ #lightblue: **from admin** \n startQKDMStream( QKDM_ID )
AQKS -[#green]> AQM ++ #lightgreen: open_connect ( src, dst )
AQM -[#green]> BQM : open_stream \n (  src, dst, KSID )
AQM --[#green]> AQKS --: < KSID >
AQKS -[#blue]> BQKS ++ #lightblue: createStream ( src, KSID, type) 
BQKS -[#green]> BQM ++ #lightgreen: open_connect ( src, dst, KSID ) 
BQM -[#green]> AQM : exchange ( KSID )
BQM --[#green]> BQKS -- : < KSID >
BQKS --[#blue]> AQKS -- : < OK >
deactivate AQKS

loop exchange keys
    AQM <-[#green]-> BQM : continuous \n QKD exchange
end


== c) Key request == 
autonumber inc A

ASAE -[#blue]> AQKS ++ #LightBlue: getKey \n (slave_SAE_ID, size, count) 
AQKS -[#green]> AQM ++ #LightGreen: get_key_ID (KSID)
AQM -[#green]->AQKS --: < KIDs > 
AQKS -[#blue]> BQKS ++ #LightBlue: reserveKeys ( master_SAE_ID, slave_SAE_ID, size, {AKID, KIDs} ) 
BQKS -[#green]> BQM ++ #LightGreen: check_key_ID (KSID, KIDs)
BQM -[#green]-> BQKS -- : < OK >
BQKS -[#blue]-> AQKS --: < OK >
AQKS -[#green]> AQM ++ #LightGreen: get_key (KSID, KIDs) 
AQM -[#green]-> AQKS --: < keys, KIDs >
AQKS -[#blue]-> ASAE --: < AKID, key >

ASAE -[#red]> BSAE :  send AKIDs  
BSAE -[#blue]> BQKS ++ #LightBlue: getKeyWithKeyIDs \n (master_SAE_ID, AKID)
BQKS -[#green]> BQM ++ #LightGreen: get_key (KSID, KIDs) 
BQM -[#green]-> BQKS --: < keys, KIDs > 
BQKS -[#blue]-> BSAE -- :  < AKID, key >

@enduml



## QKD SAE Key Exchange (Trusted Node ) 
@startuml

skinparam sequenceMessageAlign center
actor "Alice's SAE" as ASAE order 1  #lightCoral
actor "Bob's SAE" as BSAE order 5  #lightCoral
participant "Alice's QKS" as AQKS order 2 #LightBlue
participant "Bob's QKS" as BQKS order 4 #LightBlue
participant "Carol's QKS" as CQKS order 3 #lightskyblue

== a) Key request == 
autonumber 1.1
ASAE -[#blue]> AQKS ++ #LightBlue: getKey \n(slave_SAE_ID, size, count) 

group forwarding
AQKS -[#blue]> CQKS ++ #lightskyblue: forwardData \n (enc_data, next_hop, dest, KID) 
CQKS -[#blue]> BQKS ++ #lightblue: forwardData \n (enc_data, next_hop, dest, KID) 
note right: enc_data encrypted with \n a QKD derived key 
BQKS -[#blue]-> CQKS --: < OK >
CQKS -[#blue]-> AQKS --: < OK >
end

AQKS -[#blue]> BQKS ++ #LightBlue:  reserveKeys \n( master_SAE_ID, slave_SAE_ID, size, {AKID, KIDs} )
BQKS -[#blue]-> AQKS --: < ACK >
AQKS -[#blue]-> ASAE -- : < AKID, key >
ASAE -[#red]> BSAE : send AKID
BSAE -[#blue]> BQKS ++ #LightBlue: getKeyWithIDs \n(master_SAE_ID, AKID)
BQKS -[#blue]-> BSAE --: < AKID, key >

@enduml



