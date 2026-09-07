import os
import logging
from typing import Optional, Tuple

import osmnx as ox
import networkx as nx

from ..config.models import RouteConfig
from ..utils.helpers import haversine_distance_m

logger = logging.getLogger(__name__)

# Pre-baked graph covering central Chennai (Chennai Central, T Nagar, Marina
# Beach), shipped in the Docker image so demo queries in this area never
# depend on a live Overpass call -- overpass-api.de blocks some cloud/PaaS
# IP ranges (see _OVERPASS_MIRRORS below), and this sidesteps that entirely
# for the region this project is actually benchmarked/demoed against.
_REGIONAL_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "regional_seed", "chennai_central.graphml")
# Centered on the Chennai Central <-> T Nagar midpoint -- the largest of the
# pairwise query circles among {Chennai Central, T Nagar, Marina Beach}, sized
# (with margin) to fully contain the other two pairs' query circles as well.
_REGIONAL_SEED_CENTER = (13.0602095, 80.25407185)
_REGIONAL_SEED_RADIUS_M = 12000
_REGIONAL_SEED_MARGIN_M = 500  # safety buffer so we don't serve a query that clips the seed's edge

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
        self._regional_graph: Optional[nx.MultiDiGraph] = None
        self._regional_graph_load_attempted = False

    def _regional_seed(self, center_point: Tuple[float, float], radius_m: int) -> Optional[nx.MultiDiGraph]:
        dist_to_seed_center = haversine_distance_m(*center_point, *_REGIONAL_SEED_CENTER)
        if dist_to_seed_center + radius_m > _REGIONAL_SEED_RADIUS_M - _REGIONAL_SEED_MARGIN_M:
            return None  # requested area isn't fully covered by the seed graph

        if not self._regional_graph_load_attempted:
            self._regional_graph_load_attempted = True
            if os.path.exists(_REGIONAL_SEED_PATH):
                try:
                    self._regional_graph = ox.load_graphml(_REGIONAL_SEED_PATH)
                    logger.info(f"Loaded regional seed graph: {len(self._regional_graph.nodes)} nodes")
                except Exception as e:
                    logger.error(f"Regional seed graph failed to load: {e}")

        return self._regional_graph

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> nx.MultiDiGraph:
        seed = self._regional_seed(center_point, radius_m)
        if seed is not None:
            logger.info(f"Serving {center_point} radius {radius_m}m from pre-baked regional seed (no Overpass call)")
            return seed

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
