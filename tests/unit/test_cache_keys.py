"""
Unit tests for backend/app/cache.py's pure key-generation and stats logic.
No real Redis needed -- _client is monkeypatched to the "unavailable" sentinel.
"""

import pytest

from app import cache as redis_cache

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _force_redis_unavailable(monkeypatch):
    # Patch _redis() itself rather than _client -- _client=False is the
    # internal "already tried, don't retry" sentinel, but _redis() only
    # collapses it to None (the public "unavailable" signal) on a *fresh*
    # failed connection attempt. Patching the entry point is the faithful way
    # to simulate "Redis unavailable" from a test.
    monkeypatch.setattr(redis_cache, "_redis", lambda: None)
    monkeypatch.setattr(redis_cache, "_hits", 0)
    monkeypatch.setattr(redis_cache, "_misses", 0)


class TestKeyGeneration:
    def test_geocode_key_deterministic(self):
        assert redis_cache.geocode_key("Chennai") == redis_cache.geocode_key("Chennai")

    def test_geocode_key_case_and_whitespace_insensitive(self):
        assert redis_cache.geocode_key("Chennai") == redis_cache.geocode_key(" chennai ")

    def test_geocode_key_differs_for_different_locations(self):
        assert redis_cache.geocode_key("Chennai") != redis_cache.geocode_key("Coimbatore")

    def test_route_key_deterministic(self):
        k1 = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car")
        k2 = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car")
        assert k1 == k2

    def test_route_key_differs_by_route_type(self):
        k1 = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car")
        k2 = redis_cache.route_key("Chennai", "Coimbatore", "scenic", "car")
        assert k1 != k2

    def test_route_key_differs_by_departure_hour(self):
        peak = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car", 18)
        off_peak = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car", 3)
        assert peak != off_peak

    def test_geocode_and_route_keys_have_distinct_prefixes(self):
        gk = redis_cache.geocode_key("Chennai")
        rk = redis_cache.route_key("Chennai", "Coimbatore", "fastest", "car")
        assert gk.startswith("geocode:")
        assert rk.startswith("route:")


class TestGetSetWithoutRedis:
    def test_get_returns_none_when_unavailable(self):
        assert redis_cache.get(redis_cache.geocode_key("Chennai")) is None

    def test_set_is_a_noop_when_unavailable(self):
        # Must not raise even though there's no real Redis client.
        redis_cache.set(redis_cache.geocode_key("Chennai"), [13.08, 80.27])


class TestStats:
    def test_stats_reports_unavailable(self):
        stats = redis_cache.stats()
        assert stats["status"] == "unavailable"
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_pct"] == 0.0
