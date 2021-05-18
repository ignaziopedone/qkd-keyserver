# Threadsafe class with support for Nodes and SAEs into a graph 
# support routing tables printing based on graph costs

from threading import Lock
import heapq
import sys 

class Sae() : 
    def __init__(self, id: str, node : str, attr = None): 
        self.id : str = id
        self.nodeid : str = node

class Node() : 
    def __init__(self, id: str): 
        self.id : str = id
        self.adjacent : dict = {}
        self.saes : list = []


    def add_neighbor(self, neighbor : Node , cost : float) -> bool:
        if neighbor not in self.adjacent and neighbor.id != self.id : 
            self.adjacent[neighbor] = cost 
            return True
        return False 

    def remove_neighbor(self, neighbor : Node) -> bool: 
        if neighbor not in self.adjacent: 
            return False
        self.adjacent.pop(neighbor)
        return True

    def remove_sae(self, sae : Sae) -> bool: 
        if sae in self.saes :
            self.saes.remove(sae)
            return True
        return False 
    
    def add_sae(self, sae: Sae) -> bool:
        if sae not in self.saes: 
            self.saes.append(sae) 
            return True 
        return False 

    def get_neighbors(self) -> dict:
        nl = {} 
        for n, c in self.adjacent.items(): 
            nl[n.id] = c
        return nl

    def get_saes(self) -> list:
        sl = [] 
        for s in self.saes: 
            sl.append(s.id)
        return sl
    
    def get_cost(self, neighbor : Node) -> float:
       return self.adjacent[neighbor]  if neighbor in self.adjacent else sys.maxsize
    
    def update_cost (self, neighbor : Node, cost : float) -> bool: 
        if neighbor in self.adjacent: 
            if self.adjacent[neighbor] != cost:
                self.adjacent[neighbor] = cost
                return True
        return False

    def __str__(self) -> str:
        return str(self.id) + '  - Adjacent: ' + str([x.id for x in self.adjacent.keys()]) + str([c for c in self.adjacent.values()]) + '  -  Saes: ' + str([x.id for x in self.saes])


class Table() : 
    def __init__(self, dest:str, next:str, length:int, cost:float):
        self.dest : str = dest
        self.next : str = next
        self.cost : float = cost
        self.len : int = length

    def __str__(self) -> str: 
        return f'| dest : {self.dest} | next : {self.next} | len : {self.len} | cost : {self.cost}'

class Graph:
    def __init__(self, nodes : list):
        self.node_dict : dict = {}
        self.sae_dict : dict = {} 
        self.num_links : int = 0

        self.lock = {'sae' : Lock(), 'node' : Lock() }  
        self.routing_tables : dict = {}
        self.start = None 
        self.distance : dict = {}       
        self.visited : dict = {}  
        self.previous : dict = {}

        for n in nodes : 
            self.add_node(n)

    def add_node(self, node : str) -> Node:
        with self.lock['node']:
            if node not in self.node_dict: 
                new_node = Node(node)
                self.node_dict[node] = new_node
                return new_node
            return None

    def add_sae(self, sae : str, node: str) -> Sae:
        with self.lock['sae']:
            if sae not in self.sae_dict: 
                new_sae = Sae(sae, node)
                if (self.node_dict[node].add_sae(new_sae)):
                    self.sae_dict[sae] = new_sae
                    return new_sae
            return None

    def get_node(self, k : str) -> Node: 
        with self.lock['node']: 
            if k in self.node_dict:
                return self.node_dict[k]
            return None


    def add_link(self, src:str, dst:str, cost:float) -> bool:
        with self.lock['node']:
            if src != dst and src in self.node_dict and dst in self.node_dict:
                if self.node_dict[src].add_neighbor(self.node_dict[dst], cost) and self.node_dict[dst].add_neighbor(self.node_dict[src], cost):
                    self.num_links += 1
                    return True
            return False

    def get_nodes(self) -> list:
        return list(self.node_dict.keys())

    def get_saes(self) -> list:
        return list(self.sae_dict.keys())

    def remove_link(self, src:str, dst:str) -> bool: 
        with self.lock['node']:
            if src in self.node_dict and dst in self.node_dict:
                src_node = self.node_dict[src] 
                dst_node = self.node_dict[dst]
                if src_node.remove_neighbor(dst_node) and dst_node.remove_neighbor(src_node): 
                    self.num_links -= 1
                    return True
            return False 

    def remove_sae(self, s : str) -> bool : 
        with self.lock['sae']:
            if s in self.sae_dict:
                sae = self.sae_dict[s]
                if self.node_dict[sae.nodeid].remove_sae(sae) : 
                    self.sae_dict.pop(s) 
                    return True
            return False 

    def update_link(self, src:str, dst:str, cost:float) -> bool: 
        with self.lock['node']:
            if src in self.node_dict and dst in self.node_dict:
                src_node = self.node_dict[src] 
                dst_node = self.node_dict[dst]
                if src_node.update_cost(dst_node, cost) and dst_node.update_cost(src_node, cost): 
                    return True
            return False 

    def build_path(self, node:str) -> list:
        path = [node]
        while self.previous[node] is not None:
            path.append(self.previous[node])
            node = self.previous[node]

        return path

    def build_routing_tables(self, start:str) -> dict :
        with self.lock['node']:

            self.dijkstra(start)
            for key, node in self.node_dict.items() :
                dest = node.id
                if dest != start: 
                    
                    path = self.build_path(dest)
                    next = path[-2] if len(path)>=2 else ""  
                    cost = self.distance[dest] if next!="" else -1
                    rt = Table(dest, next, len(path)-1, cost) 
                    self.routing_tables[dest] = rt

            with self.lock['sae']:
                sae_rts = {} 
                for sae in self.sae_dict: 
                    n = self.sae_dict[sae].nodeid
                    if n != start:
                        sae_rts[sae] = {
                            'dest' : self.routing_tables[n].dest,
                            'next' : self.routing_tables[n].next,
                            'cost' : self.routing_tables[n].cost,
                            'len'  : self.routing_tables[n].len
                        }

            return sae_rts

    def dijkstra(self, start:str) -> None:
        self.start = start
        unvisited_queue = [] 
        # Put tuple pair into the priority queue
        for n in self.node_dict: 
            self.visited[n] = False 
            self.previous[n] = None
            self.distance[n] = sys.maxsize if n!=start else 0.0
            unvisited_queue.append((self.distance[n],n)) 
        heapq.heapify(unvisited_queue)

        while len(unvisited_queue):
            uv = heapq.heappop(unvisited_queue)
            current = uv[1]
            self.visited[current] = True
            node = self.node_dict[current]
            for next in node.adjacent:
                next_id = next.id
                if self.visited[next_id]:
                    continue
                new_dist = self.distance[current] + node.get_cost(next)
                
                if new_dist < self.distance[next_id]:
                    self.distance[next_id] = new_dist
                    self.previous[next_id]= current

            # Rebuild heap
            while len(unvisited_queue):
                heapq.heappop(unvisited_queue)
            unvisited_queue = []
            for v in self.node_dict: 
                if not self.visited[v] :
                    unvisited_queue.append((self.distance[v],v)) 
            heapq.heapify(unvisited_queue)

    def print_nodes(self) -> None: 
        for key in sorted(list(self.node_dict.keys())): 
            print(self.node_dict[key])

    def __str__(self) -> str:
        return  f'Nodes# : {len(self.node_dict)}, SAEs# : {len(self.sae_dict)}, links# = {self.num_links}'



