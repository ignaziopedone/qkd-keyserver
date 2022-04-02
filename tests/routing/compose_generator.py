import yaml 

tot = 10

compose = {
    "version" : "3.9",
    "services" : {}
}


for n in range(0,tot): 
    name = f"routing{format(n, '02d')}"
    obj = {
        "image" : "lorenzopintore/routing_test", 
        "ports" : [f"{8000+n}:7000"],
        "container_name" : name,
        "command" : [f"config_files/test{format(n, '02d')}.yaml"]#,
        #"extra_hosts" : ["host.docker.internal:host-gateway"]
    }
    compose["services"][name] = obj

    file = open(f"tests/routing/docker-compose.yaml", "w+")
    yaml.dump(compose, file)
    file.close()
