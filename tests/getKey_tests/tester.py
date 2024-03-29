import sys 
import yaml 
import os 
import time
import ast

def create_req(master:str, slave:str, number:int, size:int, number_req:int, parallel:int): 
    try:
        os.system("rm -r req")
        os.system("mkdir req")
        for i in range(0, number_req): 
            obj_list = []
            name = f"{master}{slave}-{number}-{size}-{i}" 
            for j in range(0, parallel): 
                obj_dict = {
                    "apiVersion": "qks.controller/v1",
                    "kind": "KeyRequest",
                    "metadata":
                        {"name": f"{name}-{j}"},
                    "spec": {
                        "number": number,
                        "size": size,
                        "master_SAE_ID": master, 
                        "slave_SAE_ID": slave 
                        }
                }
                obj_list.append(obj_dict)

            file = open(f"req/{name}.yaml", "w+")
            yaml.dump_all(obj_list, file, default_flow_style=False)
            file.close()
    except Exception as e: 
        print(f"Exception in create_req: {e}")

def exec_req_grep(namespace, timer, pod, name): 
    try:
        for file in os.listdir("req"): 
            start = time.time()
            os.system(f"kubectl apply -f req/{file} -n {namespace}")
            print (f"Request execution time: {time.time() - start}")
            time.sleep(timer)

        time.sleep(1)
        os.system(f"kubectl logs {pod} -n {namespace} | grep 'Request completed: {name[:-5]}' > {name}-res")
        os.system(f"kubectl logs {pod} -n {namespace} | grep 'ID list - {name[:-5]}' > {name}-ids")
    except Exception as e: 
        print(f"Exception in exec_req_grep: {e}")

def exec_req_id(namespace, timer, pod, name):
    try: 
        for file in os.listdir("reqid"): 
            os.system(f"kubectl apply -f reqid/{file} -n {namespace}")
            time.sleep(timer)

        time.sleep(2)
        os.system(f"kubectl logs {pod} -n {namespace} | grep 'Request completed: {name[:-5]}' > {name}-res")
    except Exception as e: 
        print(f"Exception in exec_req_id: {e}")


def format_res(filename):
    try:
        file = open(filename, "r")
        resOperator = []
        resQks = []
        for line in file:
            string = line.split("Request completed: ")[1]
            resOperator.append(string.split("in ")[1][:5])
            resQks.append(string[-6:])
        file.close()

        file_res = open(f"{filename.split('.')[0]}.csv", "w+")
        res_list = []
        for r1, r2 in zip(resOperator, resQks):
            file_res.write(f"{r1}, \t {r2}")
        file_res.close()
    except Exception as e: 
        print(f"Exception in format_res: {e}")

def create_id_req(filename:str):
    try: 
        os.system("rm -r reqid")
        os.system("mkdir reqid")

        file = open(filename, "r")
        master = filename[:5]
        slave = filename[5:10]

        ids_set = set()
        obj_list = []
        i = 0
        for line in file:
            sl = line.split("ID list - ")[1]
            name, slids = sl.split(" : ")
            id_list = ast.literal_eval(slids)

            for id in id_list:
                if id in ids_set:
                    continue
                else:
                    ids_set.add(id)

            obj_dict = {
                "apiVersion": "qks.controller/v1",
                "kind": "KeyRequest",
                "metadata":
                    {"name": name},
                "spec": {
                    "ids" : id_list,
                    "master_SAE_ID": master,
                    "slave_SAE_ID": slave
                    }
            }
            obj_list.append(obj_dict)
            file = open(f"reqid/{name}.yaml", "w+")
            yaml.dump(obj_dict, file)
            file.close()
    except Exception as e: 
        print(f"Exception in create_id_req: {e}")

def reset(namespace:str):
    os.system(f"kubectl get secret -n {namespace} --no-headers=true |" + " awk '/sae12sae20/{print $1}'|" + f" xargs  kubectl delete -n {namespace} secret") 
    os.system(f"kubectl get keyreq -n {namespace} --no-headers=true |" + " awk '/sae12sae20/{print $1}'|" + f" xargs  kubectl delete -n {namespace} keyreq") 

def main(): 
    command = int(input("1 for master request, 2 for slave request: "))
    namespace = input("Namespace: ")
    timer = float(input("Timer: "))
    pod = input("Operator pod name: ")
    
    reset(namespace)

    if command == 1: 
        master = "sae12"
        slave = "sae20"
        size = int(input("Key size: "))
        number = int(input("Key number for each request: "))
        number_req = int(input("Number of requests: "))
        parallel = int(input("Number of parallel requests: "))
        name = f"{master}{slave}-{number}-{size}-{number_req}"

        create_req(master, slave, number, size, number_req, parallel)
        exec_req_grep(namespace, timer, pod, name)
        format_res(f"{name}-res")
    
    elif command == 2: 
        request_name = input("Insert request name (IDs file must be in current folder): ")
        create_id_req(f"{request_name}-ids")
        exec_req_id(namespace, timer, pod, request_name)
        format_res(f"{request_name}-res")

main()