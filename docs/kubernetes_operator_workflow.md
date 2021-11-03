@startuml
skinparam sequenceMessageAlign center
entity "SAE_A01" as ASAE order 1 #lightCoral
entity "SAE_B01" as BSAE order 8 #LightBlue
participant "QKS A" as AQKS order 4 #lightCoral
participant "QKS B" as BQKS order 5 #LightBlue
participant "OPERATOR A" as AOP order 3 #lightCoral
participant "OPERATOR B" as BOP order 6 #LightBlue
participant "KEYCLOAK A" as KA order 2 #lightCoral 
participant "KEYCLOAK B" as KB order 7 #lightBlue

== Key request ==

autonumber "<b>A0"

ASAE -> ASAE++--#lightCoral: create_KeyRequest \n(req_nameA, master_SAE_ID, \n slave_SAE_ID, size, number)
?->AOP ++#lightCoral: reacts to resource creation
AOP -> AOP : retrieve_Secret\n(master_SAE_credentials)
AOP -> KA ++#lightCoral: login(master_SAE)
KA -> AOP --: < token >
AOP -> AQKS ++#lightCoral: getKey (master_SAE_ID, \nslave_SAE_ID, \nsize, number, token)
AQKS <-> BQKS ++#lightBlue: exchange_keys
deactivate BQKS
AQKS --> AOP --: < keyIDs, keys >
AOP -> AOP --: create_Secret \n (req_nameA, keyIDs, keys) 

ASAE<-? ++#lightCoral: retrieve_Secret(req_nameA) 
ASAE -> BSAE --++#lightBlue: sends keyIDs 

autonumber "<b>B0"
BSAE <- BSAE --: create_KeyRequest \n(req_nameB,master_SAE_ID, \nslave_SAE_ID, keyIDs)
BOP<-? ++#lightBlue: reacts to resource creation
BOP -> BOP : retrieve_Secret\n(slave_SAE_credentials)
BOP -> KB ++#lightBlue: login(slave_SAE)
KB -> BOP --: < token >
BOP -> BQKS ++#lightBlue: getKeyWithKeyIDs\n(master_SAE_ID, \n slave_SAE_ID, keyIDs, token)
BQKS --> BOP --: < keyIDs, keys >
BOP -> BOP --: create_Secret \n (req_nameB, keyIDs, keys) 
?->BSAE ++#lightBlue: retrieve_Secret(req_nameB)
deactivate BSAE 

@enduml