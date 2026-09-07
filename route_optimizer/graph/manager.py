import os
import logging
from typing import Tuple

import osmnx as ox
import networkx as nx

from ..config.models import RouteConfig

logger = logging.getLogger(__name__)

# Some cloud/PaaS IP ranges (Render, Railway, Heroku, etc.) get blocked by
# individual Overpass instances as an anti-abuse measure -- which one is
# blocked isn't predictable from outside that host's network, so try a few
# public mirrors in order rather than hardcoding a single one.
_OVERPASS_MIRRORS = [
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.osm.ch/api",
]

# osmnx's default request timeout is 180s -- with 3 mirrors that could burn
# up to 9 minutes on a host where every mirror hangs, well past gunicorn's
# 120s worker timeout (backend/Dockerfile). Cap each attempt so a stuck
# mirror fails fast into the next one instead of eating the whole budget.
ox.settings.requests_timeout = 25


class GraphManager:

    def __init__(self, config: RouteConfig) -> None:
        self.config = config
        os.makedirs(self.config.graph_cache_dir, exist_ok=True)

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> nx.MultiDiGraph:
        cache_name = f"graph_{center_point[0]:.6f}_{center_point[1]:.6f}_{radius_m}.graphml"
        cache_file = os.path.join(self.config.graph_cache_dir, cache_name)

        if os.path.exists(cache_file):
            logger.info(f"Loading graph from disk cache: {cache_file}")
            try:
                return ox.load_graphml(cache_file)
            except Exception as e:
                logger.error(f"Cached graph corrupt, re-downloading: {e}")

        return self._download_graph(center_point, radius_m, cache_file)

    def _download_graph(
        self, center_point: Tuple[float, float], radius_m: int, cache_file: str
    ) -> nx.MultiDiGraph:
        logger.info(f"Downloading road network at {center_point}, radius {radius_m}m")
        last_exc: Exception = RuntimeError("No Overpass mirrors configured")
        for mirror in _OVERPASS_MIRRORS:
            ox.settings.overpass_url = mirror
            try:
                graph = ox.graph_from_point(center_point, dist=radius_m, network_type='drive', simplify=True)
                ox.save_graphml(graph, cache_file)
                logger.info(f"Graph cached at {cache_file} (via {mirror})")
                return graph
            except Exception as e:
                logger.warning(f"Overpass mirror {mirror} failed: {e}")
                last_exc = e
        logger.error(f"All Overpass mirrors failed: {last_exc}")
        raise last_exc
