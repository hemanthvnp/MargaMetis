"""
Unit tests for GraphEngine's hand-rolled pathfinding algorithms.
Run with: pytest tests/unit/test_graph_engine.py -v
"""

import math

import pytest

from route_optimizer.intelligence.graph_engine import GraphEngine

pytestmark = pytest.mark.unit


class TestAlgorithmAgreement:
    """All four algorithms must agree on the shortest-path distance on the same graph."""

    def test_dijkstra_astar_bidirectional_agree_on_distance(self, small_graph):
        engine = GraphEngine(small_graph)
        d = engine.dijkstra(1, 6)
        a = engine.astar(1, 6)
        b = engine.bidirectional_astar(1, 6)

        assert d["path"] is not None
        assert a["path"] is not None
        assert b["path"] is not None
        assert math.isclose(d["distance"], a["distance"], rel_tol=1e-6)
        assert math.isclose(d["distance"], b["distance"], rel_tol=1e-6)

    def test_astar_never_explores_more_nodes_than_dijkstra(self, small_graph):
        engine = GraphEngine(small_graph)
        d = engine.dijkstra(1, 6)
        a = engine.astar(1, 6)
        assert a["nodes_explored"] <= d["nodes_explored"]

    def test_bidirectional_never_explores_more_nodes_than_dijkstra(self, small_graph):
        engine = GraphEngine(small_graph)
        d = engine.dijkstra(1, 6)
        b = engine.bidirectional_astar(1, 6)
        assert b["nodes_explored"] <= d["nodes_explored"]


class TestUnreachable:
    def test_dijkstra_returns_none_path_for_isolated_node(self, small_graph):
        small_graph.add_node(99, y=0.0, x=0.0)  # no edges — unreachable
        engine = GraphEngine(small_graph)
        r = engine.dijkstra(1, 99)
        assert r["path"] is None
        assert r["distance"] == float("inf")

    def test_astar_returns_none_path_for_isolated_node(self, small_graph):
        small_graph.add_node(99, y=0.0, x=0.0)
        engine = GraphEngine(small_graph)
        r = engine.astar(1, 99)
        assert r["path"] is None
        assert r["distance"] == float("inf")

    def test_bidirectional_returns_none_path_for_isolated_node(self, small_graph):
        small_graph.add_node(99, y=0.0, x=0.0)
        engine = GraphEngine(small_graph)
        r = engine.bidirectional_astar(1, 99)
        assert r["path"] is None
        assert r["distance"] == float("inf")


class TestSameOriginDestination:
    def test_bidirectional_same_node_zero_distance(self, small_graph):
        engine = GraphEngine(small_graph)
        r = engine.bidirectional_astar(1, 1)
        assert r["path"] == [1]
        assert r["distance"] == 0.0


class TestWeightFnInjection:
    def test_custom_weight_fn_changes_chosen_path(self, small_graph):
        engine = GraphEngine(small_graph)

        # Without a weight_fn, the toll motorway edge 2->3 (length 1000) is cheapest by raw length.
        baseline = engine.astar(1, 3)
        assert 2 in baseline["path"]

        # Inject a cost function that makes the motorway edge extremely expensive —
        # this must change the chosen path with zero graph mutation.
        def avoid_motorway(u, v, data):
            length = float(data.get("length", 1.0))
            if data.get("highway") == "motorway":
                return length * 1000.0
            return length

        routed = engine.astar(1, 3, avoid_motorway)
        assert routed["path"] != baseline["path"] or routed["distance"] != baseline["distance"]

    def test_weight_fn_does_not_mutate_graph(self, small_graph):
        edge_before = dict(small_graph.get_edge_data(1, 2)[0])
        engine = GraphEngine(small_graph)

        def cost_fn(u, v, data):
            return float(data.get("length", 1.0)) * 2.0

        engine.astar(1, 6, cost_fn)
        edge_after = dict(small_graph.get_edge_data(1, 2)[0])
        assert edge_before == edge_after


class TestYenKShortest:
    def test_returns_at_most_k_paths(self, small_graph):
        engine = GraphEngine(small_graph)
        routes = engine.yen_k_shortest(1, 6, k=3)
        assert 1 <= len(routes) <= 3

    def test_paths_are_distinct(self, small_graph):
        engine = GraphEngine(small_graph)
        routes = engine.yen_k_shortest(1, 6, k=3)
        paths = [tuple(r["path"]) for r in routes]
        assert len(paths) == len(set(paths))

    def test_first_route_matches_astar_shortest(self, small_graph):
        engine = GraphEngine(small_graph)
        shortest = engine.astar(1, 6)
        routes = engine.yen_k_shortest(1, 6, k=3)
        assert math.isclose(routes[0]["distance"], shortest["distance"], rel_tol=1e-6)

    def test_respects_custom_weight_fn(self, small_graph):
        # By raw length, the top route through node 2/3 (the tolled motorway) wins.
        # A cost function that heavily penalises tolls must push it out of first place.
        engine = GraphEngine(small_graph)
        baseline = engine.yen_k_shortest(1, 6, k=3)
        assert 2 in baseline[0]["path"] and 3 in baseline[0]["path"]

        def avoid_tolls(u, v, data):
            length = float(data.get("length", 1.0))
            return length * 1000.0 if data.get("toll") == "yes" else length

        routed = engine.yen_k_shortest(1, 6, k=3, weight_fn=avoid_tolls)
        assert not (2 in routed[0]["path"] and 3 in routed[0]["path"])


class TestBenchmark:
    def test_benchmark_output_shape(self, small_graph):
        engine = GraphEngine(small_graph)
        results = engine.benchmark(1, 6)

        for algo in ("dijkstra", "astar", "bidirectional_astar"):
            assert algo in results
            assert "time_ms" in results[algo]
            assert "distance" in results[algo]
            assert "nodes_explored" in results[algo]
            assert "path_length" in results[algo]

        assert "yen_k_shortest" in results
        assert "paths_found" in results["yen_k_shortest"]
        assert "distances" in results["yen_k_shortest"]
