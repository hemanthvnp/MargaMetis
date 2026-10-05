import logging
from typing import List, Optional, Tuple

import osmnx as ox
import networkx as nx

from .config.models import RouteConfig
from .graph.manager import GraphManager
from .intelligence.graph_engine import GraphEngine
from .speed_model import estimate_path_eta_minutes

logger = logging.getLogger(__name__)

_PRESETS = {
    "fuel": {
        "weights": {"fuel_efficiency": 0.75, "safety": 0.15, "speed": 0.05,
                    "scenic": 0.03, "comfort": 0.02, "cost": 0.0},
        "avoid": [], "prefer": [],
    },
    "green": {
        "weights": {"fuel_efficiency": 0.55, "scenic": 0.30, "safety": 0.10,
                    "speed": 0.03, "comfort": 0.02, "cost": 0.0},
        "avoid": [], "prefer": ["scenic_roads"],
    },
    # Penalises motorway/trunk/primary so A* routes through secondary/residential streets
    "avoid_main": {
        "weights": {"scenic": 0.45, "comfort": 0.25, "safety": 0.20,
                    "speed": 0.05, "fuel_efficiency": 0.03, "cost": 0.02},
        "avoid": ["highways"], "prefer": ["scenic_roads"],
    },
}


class RouteOptimizer:

    def __init__(self, config: Optional[RouteConfig] = None) -> None:
        self.config = config or RouteConfig()
        self.graph_manager = GraphManager(self.config)
        self.graph: Optional[nx.MultiDiGraph] = None

    def load_graph(
        self,
        center_point: Tuple[float, float],
        radius_m: int,
        route_points: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        logger.info(f"Loading graph at {center_point}, radius {radius_m}m")
        self.graph = self.graph_manager.load_graph(center_point, radius_m, route_points)

    def find_route(
        self,
        origin_coords: Tuple[float, float],
        dest_coords: Tuple[float, float],
        route_type: str = "shortest",
        vehicle_type: str = "car",
        time_of_day: Optional[int] = None,
    ) -> dict:
        if self.graph is None:
            raise ValueError("Graph not loaded. Call load_graph() first.")

        origin_node = ox.distance.nearest_nodes(self.graph, origin_coords[1], origin_coords[0])
        dest_node   = ox.distance.nearest_nodes(self.graph, dest_coords[1], dest_coords[0])

        engine = GraphEngine(self.graph)

        weight_fn = None
        if route_type in _PRESETS:
            from .intelligence.cost_function import CostFunctionGenerator
            weight_fn = CostFunctionGenerator(_PRESETS[route_type]).generate(self.graph)

        result = engine.astar(origin_node, dest_node, weight_fn)
        if result["path"] is None:
            raise ValueError("No path found between these locations.")

        eta_min = round(
            estimate_path_eta_minutes(self.graph, result["path"], time_of_day), 2
        )

        return {
            "path":               result["path"],
            "distance_m":         round(result["distance"], 2),
            "estimated_time_min": eta_min,
            "algorithm_time_ms":  round(result["time_ms"], 3),
            "nodes_explored":     result["nodes_explored"],
        }
