import networkx as nx
from heapq import heappush, heappop
from ..utils.helpers import get_node_coords, haversine_distance_m


class RouteResult(object):

    def __init__(self, path, distance_m):
        self.path = path
        self.distance_m = distance_m


class AStarPathfinder(object):

    def __init__(self, graph):
        self.graph = graph

    def _heuristic(self, node_a, node_b):
        coords_a = get_node_coords(self.graph, node_a)
        coords_b = get_node_coords(self.graph, node_b)

        lat_a, lon_a = coords_a[0], coords_a[1]
        lat_b, lon_b = coords_b[0], coords_b[1]

        estimated_distance = haversine_distance_m(lat_a, lon_a, lat_b, lon_b)
        return estimated_distance

    def find_shortest_path(self, start_node, end_node):
        open_set = []
        heappush(open_set, (0, start_node))
        came_from = {}
        g_score = {}
        for node in self.graph.nodes():
            g_score[node] = float('inf')
        g_score[start_node] = 0.0
        while open_set:
            current_f_score, current_node = heappop(open_set)
            if current_node == end_node:
                path = []
                total_distance = g_score[end_node]

                while current_node in came_from:
                    path.append(current_node)
                    current_node = came_from[current_node]

                path.append(start_node)
                path.reverse()

                return RouteResult(path, total_distance)
            for edge in self.graph.out_edges(current_node, data=True):
                source = edge[0]
                neighbor = edge[1]
                edge_data = edge[2]
                edge_length = edge_data.get('length', 0.0)
                tentative_g_score = g_score[current_node] + edge_length
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current_node
                    g_score[neighbor] = tentative_g_score
                    heuristic_cost = self._heuristic(neighbor, end_node)
                    f_score = tentative_g_score + heuristic_cost
                    heappush(open_set, (f_score, neighbor))
        raise nx.NetworkXNoPath(
            "No path found between {} and {}".format(start_node, end_node)
        )
