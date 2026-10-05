"""
API contract/spec tests: validate real endpoint responses against the JSON
Schemas in tests/spec/schemas.py. Runs against the small synthetic graph, so
it's fast and offline like unit tests -- it's the *shape* of the contract
being checked, not live routing correctness (that's integration/e2e's job).
"""

import jsonschema
import pytest

from app.routes import route_api
from route_optimizer.optimizer import RouteOptimizer
from tests.spec.schemas import (
    ERROR_RESPONSE,
    HEALTH_RESPONSE,
    ROUTE_BENCHMARK_RESPONSE,
    ROUTE_CALCULATE_RESPONSE,
    ROUTE_SMART_RESPONSE,
)

pytestmark = pytest.mark.spec

_ORIGIN_COORDS = (13.0827, 80.2707)
_DEST_COORDS = (13.0927, 80.2907)


def _patch_graph(monkeypatch, small_graph):
    def fake_load_graph(self, center_point, radius_m):
        self.graph = small_graph

    monkeypatch.setattr(RouteOptimizer, "load_graph", fake_load_graph)

    def fake_geocode(query):
        return _ORIGIN_COORDS if "origin" in query.lower() else _DEST_COORDS

    monkeypatch.setattr(route_api.ox, "geocode", fake_geocode)


class TestHealthSpec:
    def test_health_matches_schema(self, client):
        resp = client.get("/api/health")
        jsonschema.validate(resp.get_json(), HEALTH_RESPONSE)


class TestErrorSpec:
    def test_route_calculate_missing_fields_matches_error_schema(self, client):
        resp = client.post("/api/route/calculate", json={"origin": "X"})
        assert resp.status_code == 400
        jsonschema.validate(resp.get_json(), ERROR_RESPONSE)

    def test_route_smart_missing_fields_matches_error_schema(self, client):
        resp = client.post("/api/route/smart", json={"query": "fastest"})
        assert resp.status_code == 400
        jsonschema.validate(resp.get_json(), ERROR_RESPONSE)

    def test_route_benchmark_missing_fields_matches_error_schema(self, client):
        resp = client.post("/api/route/benchmark", json={"origin": "X"})
        assert resp.status_code == 400
        jsonschema.validate(resp.get_json(), ERROR_RESPONSE)


class TestRouteCalculateSpec:
    def test_success_response_matches_schema(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/calculate", json={
            "origin": "Origin Place", "destination": "Destination Place",
        })
        assert resp.status_code == 200
        jsonschema.validate(resp.get_json(), ROUTE_CALCULATE_RESPONSE)


class TestRouteSmartSpec:
    def test_success_response_matches_schema(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/smart", json={
            "query": "fastest route avoiding tolls",
            "origin": "Origin Place", "destination": "Destination Place",
        })
        assert resp.status_code == 200
        jsonschema.validate(resp.get_json(), ROUTE_SMART_RESPONSE)


class TestRouteBenchmarkSpec:
    def test_success_response_matches_schema(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/benchmark", json={
            "origin": "Origin Place", "destination": "Destination Place",
        })
        assert resp.status_code == 200
        jsonschema.validate(resp.get_json(), ROUTE_BENCHMARK_RESPONSE)
