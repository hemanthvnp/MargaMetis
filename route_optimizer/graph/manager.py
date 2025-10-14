import os
import logging
from typing import Tuple

import osmnx as ox
import networkx as nx
from ..config.models import RouteConfig

logger = logging.getLogger(__name__)


class GraphManager:
    """
    Manages loading and caching of road network graphs using OSMnx.

    Attributes:
        config (RouteConfig): Configuration object containing cache directory.
    """

    def __init__(self, config: RouteConfig) -> None:
        """
        Initialize the GraphManager and ensure the cache directory exists.

        Args:
            config (RouteConfig): Configuration object with graph cache settings.
        """
        self.config = config
        os.makedirs(self.config.graph_cache_dir, exist_ok=True)

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> nx.MultiDiGraph:
        """
        Load a road network graph centered at `center_point` with a given radius.
        If a cached graph exists, it loads from the cache. Otherwise, it downloads
        the graph and saves it to cache.

        Args:
            center_point (Tuple[float, float]): Latitude and longitude of the graph center.
            radius_m (int): Radius around the center point in meters.

        Returns:
            nx.MultiDiGraph: The loaded road network graph.
        """
        cache_name = f"graph_{center_point[0]:.6f}_{center_point[1]:.6f}_{radius_m}.graphml"
        cache_file = os.path.join(self.config.graph_cache_dir, cache_name)

        if os.path.exists(cache_file):
            logger.info(f"Loading graph from cache: {cache_file}")
            try:
                graph = ox.load_graphml(cache_file)
            except Exception as e:
                logger.error(f"Failed to load cached graph. Re-downloading. Error: {e}")
                graph = self._download_graph(center_point, radius_m, cache_file)
        else:
            graph = self._download_graph(center_point, radius_m, cache_file)

        return graph

    def _download_graph(self, center_point: Tuple[float, float], radius_m: int, cache_file: str) -> nx.MultiDiGraph:
        """
        Download the road network graph and save it to cache.

        Args:
            center_point (Tuple[float, float]): Latitude and longitude of the graph center.
            radius_m (int): Radius around the center point in meters.
            cache_file (str): Path to save the cached graph.

        Returns:
            nx.MultiDiGraph: The downloaded road network graph.
        """
        logger.info(f"Downloading road network for {center_point} within radius {radius_m}m...")
        try:
            graph = ox.graph_from_point(center_point, dist=radius_m, network_type='drive', simplify=True)
            ox.save_graphml(graph, cache_file)
            logger.info(f"Graph saved to cache: {cache_file}")
            return graph
        except Exception as e:
            logger.error(f"Failed to download graph: {e}")
            raise
