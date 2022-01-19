import yaml 

tot = 50

for n in range(0,tot): 
    next = n+1 if n+1 < tot else 0
    prev = n-1 if n-1 >= 0 else tot-1

    obj = {
        "qks": {
            "id" : f"qks{format(n, '02d')}", 
            "ip" : f"routing{format(n, '02d')}", # "host.docker.internal", 
            "port" : 4000
        },
        "routing" : {
            "timer" : 10, 
            "port" : 7000, #8000+n,
            "ip" : f"routing{format(n, '02d')}", #"host.docker.internal"
        },
        "neighbors" : [
            {"id" : f"qks{format(next, '02d')}",
            "routing_address": {"ip": f"routing{format(next, '02d')}", "port" :  7000}},
            {"id" : f"qks{format(prev, '02d')}",
            "routing_address": {"ip": f"routing{format(prev, '02d')}", "port" :  7000}}    
        ]
    }

    file = open(f"config_files/test{format(n, '02d')}.yaml", "w+")
    yaml.dump(obj, file)
    file.close()
