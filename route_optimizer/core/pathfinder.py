from dataclasses import dataclass
from heapq import heappush, heappop
from typing import Any, List, Tuple, Dict
import logging

import networkx as nx
from tqdm import tqdm
from ..utils.helpers import get_node_coords, haversine_distance_m


@dataclass(frozen=True)
class RouteResult:
    """
    Represents the result of a route search.

    Attributes:
        path (List[Any]): Ordered list of nodes from start to end.
        distance_m (float): Total distance of the path in meters.
    """
    path: List[Any]
    distance_m: float


class AStarPathfinder:
    """
    Implements the A* pathfinding algorithm on a NetworkX graph with:
    - Optimization to avoid duplicate nodes in the open set
    - logging
    - Progress bar for large graphs
    """

    def __init__(self, graph: nx.MultiDiGraph, enable_logging: bool = False, show_progress: bool = False) -> None:
        """
        Initialize the pathfinder with a graph.

        Args:
            graph (nx.MultiDiGraph): Graph on which to perform pathfinding.
            enable_logging (bool, optional): Enable debug logging. Defaults to False.
            show_progress (bool, optional): Show a progress bar during search. Defaults to False.
        """
        self.graph = graph
        self.show_progress = show_progress
        self.logger = logging.getLogger(self.__class__.__name__)
        if enable_logging:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.WARNING)

    def _heuristic(self, node_a: Any, node_b: Any) -> float:
        """
        Compute the heuristic estimate (straight-line distance) between two nodes.

        Args:
            node_a: Start node.
            node_b: End node.

        Returns:
            float: Estimated distance in meters.
        """
        lat_a, lon_a = get_node_coords(self.graph, node_a)
        lat_b, lon_b = get_node_coords(self.graph, node_b)
        return haversine_distance_m(lat_a, lon_a, lat_b, lon_b)

    def find_shortest_path(self, start_node: Any, end_node: Any) -> RouteResult:
        """
        Find the shortest path from start_node to end_node using A*.

        Args:
            start_node: Node to start from.
            end_node: Target node.

        Returns:
            RouteResult: Contains the path and total distance.

        Raises:
            nx.NetworkXNoPath: If no path exists between start_node and end_node.
        """
        open_set: List[Tuple[float, Any]] = []
        heappush(open_set, (0.0, start_node))

        came_from: Dict[Any, Any] = {}
        g_score: Dict[Any, float] = {node: float('inf') for node in self.graph.nodes()}
        g_score[start_node] = 0.0

        open_set_f_score: Dict[Any, float] = {start_node: 0.0}

        self.logger.info(f"Starting A* from {start_node} to {end_node}")

        total_nodes = self.graph.number_of_nodes()
        pbar = tqdm(total=total_nodes, desc="Nodes expanded") if self.show_progress else None

        while open_set:
            current_f_score, current_node = heappop(open_set)
            open_set_f_score.pop(current_node, None)

            self.logger.info(f"Expanding node {current_node} with f_score {current_f_score:.2f}")
            if pbar:
                pbar.update(1)

            if current_node == end_node:
                path = []
                total_distance = g_score[end_node]
                while current_node in came_from:
                    path.append(current_node)
                    current_node = came_from[current_node]
                path.append(start_node)
                path.reverse()

                self.logger.info(f"Path found: {path} with distance {total_distance:.2f} meters")
                if pbar:
                    pbar.close()
                return RouteResult(path, total_distance)

            for _, neighbor, edge_data in self.graph.out_edges(current_node, data=True):
                edge_length = edge_data.get('length', 0.0)
                tentative_g_score = g_score[current_node] + edge_length

                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current_node
                    g_score[neighbor] = tentative_g_score
                    f_score = tentative_g_score + self._heuristic(neighbor, end_node)

                    if f_score < open_set_f_score.get(neighbor, float('inf')):
                        heappush(open_set, (f_score, neighbor))
                        open_set_f_score[neighbor] = f_score
                        self.logger.info(f"Pushing neighbor {neighbor} with f_score {f_score:.2f}")

        if pbar:
            pbar.close()
        raise nx.NetworkXNoPath(f"No path found between {start_node} and {end_node}")
