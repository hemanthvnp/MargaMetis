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

    def find_route(
        self, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float], route_type: str = "shortest", time_of_day: int = 17, vehicle_type: str = "car"
    ) -> dict:
        """
        Find a route of the specified type and predict traffic/time.

        Args:
            origin_coords (Tuple[float, float]): Latitude and longitude of the start point.
            dest_coords (Tuple[float, float]): Latitude and longitude of the end point.
            route_type (str): Type of route ('shortest', 'cost', 'fuel', 'green', 'traffic_free').
            time_of_day (int): Hour of day (0-23) for traffic prediction.

        Returns:
            dict: Route details, traffic prediction, and best time info.
        """
        if self.graph is None:
            raise ValueError("Graph not loaded. Call `load_graph()` first.")

        start_node = ox.distance.nearest_nodes(self.graph, origin_coords[1], origin_coords[0])
        end_node = ox.distance.nearest_nodes(self.graph, dest_coords[1], dest_coords[0])
        logger.info(f"Nearest nodes: Start={start_node}, End={end_node}")

        pathfinder = AStarPathfinder(self.graph, enable_logging=True, show_progress=True)
        if route_type == "shortest":
            result = pathfinder.find_shortest_path(start_node, end_node)
        elif route_type == "cost":
            result = pathfinder.find_cost_efficient_path(start_node, end_node)
        elif route_type == "fuel":
            result = pathfinder.find_fuel_efficient_path(start_node, end_node)
        elif route_type == "green":
            result = pathfinder.find_green_path(start_node, end_node)
        elif route_type == "traffic_free":
            result = pathfinder.find_traffic_free_path(start_node, end_node)
        else:
            raise ValueError(f"Unknown route_type: {route_type}")

        # Traffic prediction
        from route_optimizer.traffic.predictor import TrafficPredictor
        traffic_model = TrafficPredictor()
        traffic = traffic_model.predict_traffic(result.path, time_of_day)
        # Average speeds in km/h for each vehicle type
        avg_speeds = {
            "car": 40,
            "bike": 25,
            "bus": 30,
            "truck": 25,
            "auto": 35
        }
        speed = avg_speeds.get(vehicle_type, 40)
        base_time = result.distance_m / 1000 / speed * 60  # time in min
        travel_time = traffic_model.estimate_travel_time(result.path, base_time, traffic)
        best_hour, best_time = traffic_model.best_time_for_route(result.path, base_time)

        return {
            "path": result.path,
            "distance_m": result.distance_m,
            "traffic": traffic,
            "estimated_time_min": round(travel_time, 2),
            "best_hour": best_hour,
            "best_time_min": round(best_time, 2)
        }
