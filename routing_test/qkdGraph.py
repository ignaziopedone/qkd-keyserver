# Threadsafe class with support for Nodes and SAEs into a graph 
# support routing tables printing based on graph costs

from threading import Lock
import heapq
import sys 

class Node() : 
    def __init__(self, id): 
        self.id = id
        self.adjacent = {}
        self.saes = []


    def add_neighbor(self, neighbor, cost):
        if neighbor not in self.adjacent and neighbor.id != self.id : 
            self.adjacent[neighbor] = cost 
            return True
        return False 

    def remove_neighbor(self, neighbor): 
        if neighbor not in self.adjacent: 
            return False
        self.adjacent.pop(neighbor)
        return True

    def remove_sae(self, sae): 
        if sae in self.saes :
            self.saes.remove(sae)
            return True
        return False 
    
    def add_sae(self, sae):
        if sae not in self.saes: 
            self.saes.append(sae) 
            return True 
        return False 

    def get_neighbors(self):
        nl = {} 
        for n, c in self.adjacent.items(): 
            nl[n.id] = c
        return nl

    def get_saes(self):
        sl = [] 
        for s in self.saes: 
            sl.append(s.id)
        return sl
    
    def get_cost(self, neighbor) :
       return self.adjacent[neighbor]  if neighbor in self.adjacent else sys.maxsize
    
    def update_cost (self, neighbor, cost): 
        if neighbor in self.adjacent: 
            if self.adjacent[neighbor] != cost:
                self.adjacent[neighbor] = cost
                return True
        return False


    def __str__(self):
        return str(self.id) + '  - Adjacent: ' + str([x.id for x in self.adjacent.keys()]) + str([c for c in self.adjacent.values()]) + '  -  Saes: ' + str([x.id for x in self.saes])

class Sae() : 
    def __init__(self, id, node, attr = None): 
        self.id = id
        self.nodeid = node

class Table() : 
    def __init__(self, dest, next, length, cost):
        self.dest = dest
        self.next = next
        self.cost = cost
        self.len = length

    def __str__(self): 
        return f'| dest : {self.dest} | next : {self.next} | len : {self.len} | cost : {self.cost}'

class Graph:
    def __init__(self, nodes):
        self.node_dict = {}
        self.sae_dict = {} 
        self.num_links = 0

        self.lock = {'sae' : Lock(), 'node' : Lock() }  
        self.routing_tables = {}
        self.start = None 
        self.distance = {}       
        self.visited = {}  
        self.previous = {}

        for n in nodes : 
            self.add_node(n)

    def add_node(self, node):
        with self.lock['node']:
            if node not in self.node_dict: 
                new_node = Node(node)
                self.node_dict[node] = new_node
                return new_node
            return None

    def add_sae(self, sae, node):
        with self.lock['sae']:
            if sae not in self.sae_dict: 
                new_sae = Sae(sae, node)
                if (self.node_dict[node].add_sae(new_sae)):
                    self.sae_dict[sae] = new_sae
                    return new_sae
            return None

    def get_node(self, k): 
        with self.lock['node']: 
            if k in self.node_dict:
                return self.node_dict[k]
            return None


    def add_link(self, src, dst, cost):
        with self.lock['node']:
            if src != dst and src in self.node_dict and dst in self.node_dict:
                if self.node_dict[src].add_neighbor(self.node_dict[dst], cost) and self.node_dict[dst].add_neighbor(self.node_dict[src], cost):
                    self.num_links += 1
                    return True
            return False

    def get_nodes(self):
        return list(self.node_dict.keys())

    def get_saes(self):
        return list(self.sae_dict.keys())

    def remove_link(self, src, dst): 
        with self.lock['node']:
            if src in self.node_dict and dst in self.node_dict:
                src_node = self.node_dict[src] 
                dst_node = self.node_dict[dst]
                if src_node.remove_neighbor(dst_node) and dst_node.remove_neighbor(src_node): 
                    self.num_links -= 1
                    return True
            return False 

    def remove_sae(self, s): 
        with self.lock['sae']:
            if s in self.sae_dict:
                sae = self.sae_dict[s]
                if self.node_dict[sae.nodeid].remove_sae(sae) : 
                    self.sae_dict.pop(s) 
                    return True
            return False 

    def update_link(self, src, dst, cost): 
        with self.lock['node']:
            if src in self.node_dict and dst in self.node_dict:
                src_node = self.node_dict[src] 
                dst_node = self.node_dict[dst]
                if src_node.update_cost(dst_node, cost) and dst_node.update_cost(src_node, cost): 
                    return True
            return False 

    def build_path(self, node):
        path = [node]
        while self.previous[node] is not None:
            path.append(self.previous[node])
            node = self.previous[node]

        return path


    def build_routing_tables(self, start) :
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

    def dijkstra(self, start):
        self.start = start
        unvisited_queue = [] 
        # Put tuple pair into the priority queue
        for n in self.node_dict: 
            self.visited[n] = False 
            self.previous[n] = None
            self.distance[n] = sys.maxsize if n!=start else 0
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

    def print_nodes(self): 
        for key in sorted(list(self.node_dict.keys())): 
            print(self.node_dict[key])

    def __str__(self):
        return  f'Nodes# : {len(self.node_dict)}, SAEs# : {len(self.sae_dict)}, links# = {self.num_links}'



