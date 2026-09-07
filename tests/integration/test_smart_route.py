"""
Integration tests for POST /api/route/smart -- the NL-query -> cost-function
-> ranked-routes pipeline, exercised end-to-end against the small synthetic
graph (no live OSM download, no live Groq call -- rule-based fallback only,
see tests/conftest.py::_no_groq_key).
"""

import pytest

from app.routes import route_api
from route_optimizer.intelligence.graph_engine import GraphEngine
from route_optimizer.optimizer import RouteOptimizer

pytestmark = pytest.mark.integration

_ORIGIN_COORDS = (13.0827, 80.2707)   # small_graph node 1
_DEST_COORDS = (13.0927, 80.2907)     # small_graph node 6


def _patch_graph(monkeypatch, small_graph):
    monkeypatch.setattr(route_api, "optimizer", None)

    def fake_load_graph(self, center_point, radius_m):
        self.graph = small_graph

    monkeypatch.setattr(RouteOptimizer, "load_graph", fake_load_graph)

    def fake_geocode(query):
        return _ORIGIN_COORDS if "origin" in query.lower() else _DEST_COORDS

    monkeypatch.setattr(route_api.ox, "geocode", fake_geocode)


class TestSmartRoute:
    def test_missing_fields_returns_400(self, client):
        resp = client.post("/api/route/smart", json={"query": "fastest route"})
        assert resp.status_code == 400

    def test_fastest_query_returns_ranked_route(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "fastest route avoiding tolls",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["routes"]) >= 1
        assert "tolls" in data["constraints"]["avoid"]
        assert data["cost_formula"].startswith("cost = ")

    def test_route_response_has_score_breakdown(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "scenic relaxing drive",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        data = resp.get_json()
        route = data["routes"][0]
        for key in ("speed", "safety", "scenic", "comfort", "fuel_access", "toll_cost", "composite"):
            assert key in route["score"]

    def test_empty_query_falls_back_to_default_route_description(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True


class TestSmartRouteMultipleCandidates:
    """/route/smart uses Yen's K-Shortest (not a single A*) when there are no
    waypoints, so a graph with genuinely distinct paths should surface more
    than one ranked, labeled route option."""

    def test_no_waypoint_query_returns_multiple_distinct_routes(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        routes = data["routes"]

        assert len(routes) >= 2
        # Distinct candidates, not the same path repeated
        assert len({r["distance_m"] for r in routes}) == len(routes)

    def test_routes_are_sequentially_ranked_with_unique_ids(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        routes = resp.get_json()["routes"]

        assert [r["rank"] for r in routes] == list(range(1, len(routes) + 1))
        assert len({r["route_id"] for r in routes}) == len(routes)

    def test_max_routes_from_constraints_limits_route_count(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        # max_routes comes from the extracted constraints (LLM or rule-based),
        # not the raw request body -- patch extraction directly to control it.
        monkeypatch.setattr(
            route_api.ConstraintEngine, "extract_constraints",
            lambda self, query: {
                "weights": {"speed": 0.4, "safety": 0.2, "fuel_efficiency": 0.15,
                            "scenic": 0.05, "comfort": 0.15, "cost": 0.05},
                "avoid": [], "prefer": [], "waypoints": [],
                "vehicle_type": "car", "time_of_day": None,
                "max_routes": 1,
                "clarification_needed": False, "clarification_question": None,
            },
        )
        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["routes"]) == 1

    def test_falls_back_to_single_astar_route_when_yen_finds_nothing(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        monkeypatch.setattr(GraphEngine, "yen_k_shortest", lambda self, *a, **kw: [])

        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": "Origin Place",
            "destination": "Destination Place",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["routes"]) == 1
