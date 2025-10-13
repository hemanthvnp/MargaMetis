import os
import logging
import osmnx as ox
import networkx as nx
from typing import Tuple

from ..config.models import RouteConfig

logger = logging.getLogger(__name__)

class GraphManager:
    def __init__(self, config: RouteConfig):
        self.config = config
        os.makedirs(config.graph_cache_dir, exist_ok=True)

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> nx.MultiDiGraph:
        cache_name = f"graph_{center_point[0]:.2f}_{center_point[1]:.2f}_{radius_m}.graphml"
        cache_file = os.path.join(self.config.graph_cache_dir, cache_name)

        if os.path.exists(cache_file):
            logger.info(f"Loading graph from cache: {cache_file}")
            graph = ox.load_graphml(cache_file)
        else:
            logger.info(f"Downloading road network for {center_point}...")
            graph = ox.graph_from_point(center_point, dist=radius_m, network_type='drive', simplify=True)
            ox.save_graphml(graph, cache_file)
            logger.info(f"Graph saved to cache: {cache_file}")
        
        return graph