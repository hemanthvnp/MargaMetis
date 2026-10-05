import os
import logging
from typing import Tuple

from flask import current_app, has_app_context
import osmnx as ox
import networkx as nx

from ..config.models import RouteConfig
from .spatial_store import bbox_from_center, load_spatial_graph, persist_graph

logger = logging.getLogger(__name__)


class GraphManager:

    def __init__(self, config: RouteConfig) -> None:
        self.config = config
        os.makedirs(self.config.graph_cache_dir, exist_ok=True)

    def load_graph(self, center_point: Tuple[float, float], radius_m: int) -> nx.MultiDiGraph:
        cache_name = f"graph_{center_point[0]:.6f}_{center_point[1]:.6f}_{radius_m}.graphml"
        cache_file = os.path.join(self.config.graph_cache_dir, cache_name)

        if (
            has_app_context()
            and current_app.extensions["sqlalchemy"].engine.dialect.name == "postgresql"
        ):
            return self._load_postgis_graph(center_point, radius_m, cache_file)

        if os.path.exists(cache_file):
            logger.info(f"Loading graph from disk cache: {cache_file}")
            try:
                return ox.load_graphml(cache_file)
            except Exception as e:
                logger.error(f"Cached graph corrupt, re-downloading: {e}")

        return self._download_graph(center_point, radius_m, cache_file)

    def _load_postgis_graph(
        self,
        center_point: Tuple[float, float],
        radius_m: int,
        cache_file: str,
    ) -> nx.MultiDiGraph:
        engine = current_app.extensions["sqlalchemy"].engine
        bbox = bbox_from_center(center_point, radius_m)
        graph = load_spatial_graph(engine, bbox, center_point, radius_m)
        if graph.number_of_edges():
            logger.info(
                "Loaded request graph from PostGIS: %s nodes, %s edges",
                graph.number_of_nodes(),
                graph.number_of_edges(),
            )
            return graph

        if os.path.exists(cache_file):
            logger.info("No PostGIS coverage; loading existing GraphML cache")
            try:
                graph = ox.load_graphml(cache_file)
            except Exception as exc:
                logger.error("Cached graph is corrupt; downloading replacement: %s", exc)
                graph = self._download_graph(center_point, radius_m, cache_file=None)
        else:
            logger.info("No PostGIS coverage; downloading OSM graph")
            graph = self._download_graph(center_point, radius_m, cache_file=None)

        connection = engine.raw_connection()
        try:
            persist_graph(connection, graph)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return graph

    def _download_graph(
        self,
        center_point: Tuple[float, float],
        radius_m: int,
        cache_file: str | None,
    ) -> nx.MultiDiGraph:
        logger.info(f"Downloading road network at {center_point}, radius {radius_m}m")
        try:
            graph = ox.graph_from_point(center_point, dist=radius_m, network_type='drive', simplify=True)
            if cache_file:
                ox.save_graphml(graph, cache_file)
                logger.info(f"Graph cached at {cache_file}")
            return graph
        except Exception as e:
            logger.error(f"Graph download failed: {e}")
            raise
