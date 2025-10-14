import logging
from typing import Tuple, Optional

import osmnx as ox
import networkx as nx

from .config.models import RouteConfig
from .graph.manager import GraphManager
from .core.pathfinder import AStarPathfinder, RouteResult

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """
    High-level class to manage road network graphs and compute shortest routes
    using A* pathfinding on OSMnx road networks.
    """

    def __init__(self, config: Optional[RouteConfig] = None) -> None:
        """
        Initialize the RouteOptimizer.

        Args:
            config (Optional[RouteConfig]): Configuration object for graph caching.
                                            Defaults to a new RouteConfig.
        """
        self.config: RouteConfig = config or RouteConfig()
        self.graph_manager: GraphManager = GraphManager(self.config)
        self.graph: Optional[nx.MultiDiGraph] = None

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> None:
        """
        Load or download a road network graph centered at `center_point` with the specified radius.

        Args:
            center_point (Tuple[float, float]): Latitude and longitude of the center point.
            radius_m (int): Radius around the center point in meters.
        """
        logger.info(f"Loading graph centered at {center_point} with radius {radius_m} meters...")
        self.graph = self.graph_manager.load_graph(center_point, radius_m)

    def find_shortest_route(
        self, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float]
    ) -> RouteResult:
        """
        Find the shortest path between origin and destination coordinates.

        Args:
            origin_coords (Tuple[float, float]): Latitude and longitude of the start point.
            dest_coords (Tuple[float, float]): Latitude and longitude of the end point.

        Returns:
            RouteResult: Contains the path as a list of nodes and the total distance in meters.

        Raises:
            ValueError: If the graph has not been loaded yet.
        """
        if self.graph is None:
            raise ValueError("Graph not loaded. Call `load_graph()` first.")

        # Get nearest graph nodes to the coordinates
        start_node = ox.distance.nearest_nodes(self.graph, origin_coords[1], origin_coords[0])
        end_node = ox.distance.nearest_nodes(self.graph, dest_coords[1], dest_coords[0])
        logger.info(f"Nearest nodes: Start={start_node}, End={end_node}")

        # Compute shortest path using A*
        pathfinder = AStarPathfinder(self.graph, enable_logging=True, show_progress=True)
        result = pathfinder.find_shortest_path(start_node, end_node)
        logger.info(f"Shortest path found: {result.path} (Distance: {result.distance_m:.2f} m)")

        return result
