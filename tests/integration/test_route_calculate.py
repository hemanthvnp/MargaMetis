"""
Integration tests for POST /api/route/calculate.

Uses a real Flask test client + real sqlite DB + the small synthetic graph
(no live OSM download). ox.geocode is monkeypatched to fixed coordinates
that sit exactly on small_graph's node 1 / node 6, so nearest_nodes resolves
deterministically. Redis is real when reachable (cache_hit assertions are
skipped otherwise via redis_up).
"""

import time

import pytest

from app.routes import route_api
from route_optimizer.optimizer import RouteOptimizer

pytestmark = pytest.mark.integration

_ORIGIN_COORDS = (13.0827, 80.2707)   # matches small_graph node 1
_DEST_COORDS = (13.0927, 80.2907)     # matches small_graph node 6


def _patch_graph(monkeypatch, small_graph):
    def fake_load_graph(self, center_point, radius_m, route_points=None):
        self.graph = small_graph

    monkeypatch.setattr(RouteOptimizer, "load_graph", fake_load_graph)

    def fake_geocode(query):
        return _ORIGIN_COORDS if "origin" in query.lower() else _DEST_COORDS

    monkeypatch.setattr(route_api.ox, "geocode", fake_geocode)


class TestRouteCalculate:
    def test_missing_fields_returns_400(self, client):
        resp = client.post("/api/route/calculate", json={"origin": "Origin Place"})
        assert resp.status_code == 400

    def test_successful_route_calculation(self, monkeypatch, client, small_graph):
        _patch_graph(monkeypatch, small_graph)
        resp = client.post("/api/route/calculate", json={
            "origin": "Origin Place",
            "destination": "Destination Place",
            "route_type": "shortest",
            "vehicle_type": "car",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["distance_m"] > 0
        assert data["path_nodes"] >= 2
        assert data["confidence"] is not None
        assert data["origin"]["name"] == "Origin Place"
        assert data["destination"]["name"] == "Destination Place"

    def test_search_history_persisted(self, monkeypatch, client, flask_app, small_graph):
        _patch_graph(monkeypatch, small_graph)
        client.post("/api/route/calculate", json={
            "origin": "Origin Place",
            "destination": "Destination Place",
        })

        from app.models import SearchHistory
        with flask_app.app_context():
            rows = SearchHistory.query.filter_by(origin="Origin Place").all()
            assert len(rows) == 1
            assert rows[0].destination == "Destination Place"
            assert rows[0].distance_m > 0
            assert rows[0].origin_geom is None
            assert rows[0].dest_geom is None

    def test_cache_hit_on_repeat_query(self, monkeypatch, client, small_graph, redis_up):
        if not redis_up:
            pytest.skip("Redis not reachable -- cache_hit behaviour can't be exercised")

        _patch_graph(monkeypatch, small_graph)
        # Unique per test run -- the route cache key is derived from these
        # strings with a 1h TTL, so reusing fixed literals would make this
        # test flaky across repeated suite runs within that window.
        nonce = time.time_ns()
        payload = {
            "origin": f"Origin Place Unique {nonce}",
            "destination": f"Destination Place Unique {nonce}",
            "route_type": "shortest",
            "vehicle_type": "car",
        }
        first = client.post("/api/route/calculate", json=payload).get_json()
        second = client.post("/api/route/calculate", json=payload).get_json()

        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert second["distance_m"] == first["distance_m"]
