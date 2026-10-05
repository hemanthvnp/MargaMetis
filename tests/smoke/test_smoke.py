"""
Smoke tests: is the app alive and wired together correctly?
Fast, sqlite-backed, no Redis/network required. These should be the first
thing run in CI -- if these fail, nothing else is worth running.
"""

import pytest

from route_optimizer.intelligence.graph_engine import GraphEngine

pytestmark = pytest.mark.smoke


class TestAppFactory:
    def test_app_creates_successfully(self, flask_app):
        assert flask_app is not None

    def test_all_blueprints_registered(self, flask_app):
        names = {bp for bp in flask_app.blueprints}
        assert names == {"routes", "health", "auth", "admin", "user"}


class TestHealthEndpoints:
    def test_health_check_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"

    def test_cache_stats_ok(self, client):
        resp = client.get("/api/cache/stats")
        assert resp.status_code == 200
        assert "status" in resp.get_json()


class TestGraphEngineTrivialRoute:
    def test_trivial_three_node_route(self, tiny_graph):
        engine = GraphEngine(tiny_graph)
        result = engine.astar(1, 3)
        assert result["path"] == [1, 2, 3]
        assert result["distance"] == pytest.approx(1000.0)

    def test_yen_k_shortest_wired_and_callable(self, tiny_graph):
        # Just the wiring: on a single-path 3-node line, k=3 can only ever
        # surface the one path -- this is a liveness check, not a diversity one.
        engine = GraphEngine(tiny_graph)
        routes = engine.yen_k_shortest(1, 3, k=3)
        assert len(routes) == 1
        assert routes[0]["path"] == [1, 2, 3]


class TestSmartRouteWired:
    def test_smart_route_endpoint_does_not_500(self, monkeypatch, client, tiny_graph):
        from app.routes import route_api
        from route_optimizer.optimizer import RouteOptimizer

        monkeypatch.setattr(route_api, "optimizer", None)
        monkeypatch.setattr(RouteOptimizer, "load_graph",
                             lambda self, center_point, radius_m: setattr(self, "graph", tiny_graph))
        monkeypatch.setattr(
            route_api.ox, "geocode",
            lambda q: (13.08, 80.27) if "origin" in q.lower() else (13.10, 80.29),
        )

        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": "Origin Place", "destination": "Destination Place",
        })
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
