from concurrent.futures import ThreadPoolExecutor
from threading import Event

import networkx as nx
import pytest

from app.routes import route_api
from route_optimizer.intelligence.graph_engine import GraphEngine


pytestmark = pytest.mark.integration


def _line_graph(first_node, lat, lon):
    graph = nx.MultiDiGraph()
    graph.add_node(first_node, x=lon, y=lat)
    graph.add_node(first_node + 1, x=lon + 0.001, y=lat)
    graph.add_edge(
        first_node,
        first_node + 1,
        length=100.0,
        highway="residential",
    )
    return graph


def test_concurrent_requests_route_on_their_own_graphs(monkeypatch):
    graph_a = _line_graph(101, 13.0, 80.0)
    graph_b = _line_graph(201, 14.0, 81.0)
    graph_a_loaded = Event()
    graph_b_loaded = Event()

    class RequestOptimizer:
        def __init__(self):
            self.graph = None

        def load_graph(self, center_point, radius_m, route_points=None):
            if center_point[0] < 13.5:
                self.graph = graph_a
                graph_a_loaded.set()
                assert graph_b_loaded.wait(timeout=5)
            else:
                assert graph_a_loaded.wait(timeout=5)
                self.graph = graph_b
                graph_b_loaded.set()

    monkeypatch.setattr(route_api, "RouteOptimizer", RequestOptimizer)

    def route(origin, destination, expected_nodes):
        optimizer = route_api._load_graph_for_coords(origin, destination)
        result = GraphEngine(optimizer.graph).astar(*expected_nodes)
        return result["path"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            route, (13.0, 80.0), (13.0, 80.001), (101, 102)
        )
        second = executor.submit(
            route, (14.0, 81.0), (14.0, 81.001), (201, 202)
        )

        assert first.result(timeout=10) == [101, 102]
        assert second.result(timeout=10) == [201, 202]
