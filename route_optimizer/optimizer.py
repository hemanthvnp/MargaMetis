import logging
import osmnx as ox
import networkx as nx
from typing import Tuple

from .config.models import RouteConfig
from .graph.manager import GraphManager
from .core.pathfinder import AStarPathfinder, RouteResult

logger = logging.getLogger(__name__)

class RouteOptimizer:

    def __init__(self, config: RouteConfig = None):
        self.config = config or RouteConfig()
        self.graph_manager = GraphManager(self.config)
        self.graph: nx.MultiDiGraph = None

    def load_graph(self, center_point: Tuple[float, float], radius_m: int):
        self.graph = self.graph_manager.load_graph(center_point, radius_m)

    def find_shortest_route(self, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float]) -> RouteResult:
        if self.graph is None:
            raise ValueError("Graph not loaded. Call load_graph() first.")
        start_node = ox.distance.nearest_nodes(self.graph, origin_coords[1], origin_coords[0])
        end_node = ox.distance.nearest_nodes(self.graph, dest_coords[1], dest_coords[0])
        logger.info(f"Graph nodes: Start={start_node}, End={end_node}")
        pathfinder = AStarPathfinder(self.graph)
        result = pathfinder.find_shortest_path(start_node, end_node)
        return result