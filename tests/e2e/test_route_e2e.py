"""
Backend-only end-to-end tests: real Flask app + real Redis (if reachable) +
real OSM data (live geocoding + live/cached graph download via GraphManager,
exactly the production code path -- nothing mocked).

Slow and network-dependent by design -- run with `pytest -m e2e`.
First run downloads a real Chennai-area road graph (~tens of MB, ~20-40s);
subsequent runs hit the on-disk graph_cache/ and are fast.
"""

import pytest

pytestmark = pytest.mark.e2e

_ORIGIN = "Chennai Central Railway Station, Chennai, India"
_DESTINATION = "Chennai International Airport, Chennai, India"


class TestRouteCalculateE2E:
    def test_real_route_between_chennai_landmarks(self, client):
        resp = client.post("/api/route/calculate", json={
            "origin": _ORIGIN,
            "destination": _DESTINATION,
            "route_type": "shortest",
            "vehicle_type": "car",
        })
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["success"] is True
        # Real Chennai Central -> Airport is a genuine multi-km drive.
        assert 8_000 < data["distance_m"] < 40_000
        assert data["path_nodes"] > 10
        assert data["estimated_time_min"] > 0
        assert data["confidence"] is not None
        assert data["confidence"]["risk_level"] in ("Low", "Medium", "High")


class TestSmartRouteE2E:
    def test_real_smart_route_avoiding_tolls(self, client):
        resp = client.post("/api/route/smart", json={
            "query": "fastest route avoiding tolls",
            "origin": _ORIGIN,
            "destination": _DESTINATION,
        })
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["success"] is True
        assert len(data["routes"]) >= 1
        assert "tolls" in data["constraints"]["avoid"]
        best = data["routes"][0]
        assert best["distance_m"] > 0
        assert best["eta_min"] > 0

    def test_real_smart_route_via_yen_returns_valid_candidates(self, client):
        # No "via" waypoint -> the live /route/smart path runs Yen's K-Shortest
        # against the real Chennai road graph. How many *distinct* candidates
        # survive is topology-dependent -- RouteRanker._deduplicate() correctly
        # collapses near-identical alternates (within 3% distance / 2%
        # composite score), so this asserts validity/shape, not a fixed count.
        resp = client.post("/api/route/smart", json={
            "query": "fastest route",
            "origin": _ORIGIN,
            "destination": _DESTINATION,
        })
        assert resp.status_code == 200
        data = resp.get_json()

        routes = data["routes"]
        assert len(routes) >= 1
        assert len({r["route_id"] for r in routes}) == len(routes)
        assert [r["rank"] for r in routes] == list(range(1, len(routes) + 1))
        for r in routes:
            assert r["distance_m"] > 0
            assert r["eta_min"] > 0
        if len(routes) > 1:
            assert len({r["distance_m"] for r in routes}) == len(routes)
