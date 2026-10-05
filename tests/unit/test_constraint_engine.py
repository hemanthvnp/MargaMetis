"""
Unit tests for the rule-based NL constraint extraction fallback
(route_optimizer/intelligence/constraint_engine.py::extract_constraints).

GROQ_API_KEY is forced absent (see tests/conftest.py::_no_groq_key) so every
call here deterministically exercises _rule_extract, never a live LLM call.
"""

import pytest

from route_optimizer.intelligence.constraint_engine import extract_constraints

pytestmark = pytest.mark.unit


class TestWeightsAlwaysNormalised:
    @pytest.mark.parametrize("query", [
        "fastest route avoiding tolls",
        "scenic drive to the beach",
        "safe night drive alone",
        "heavy truck, need wide roads",
        "xyz",
        "",
    ])
    def test_weights_sum_to_one(self, query):
        result = extract_constraints(query)
        total = sum(result["weights"].values())
        assert abs(total - 1.0) < 1e-3


class TestAvoidPrefer:
    def test_avoid_tolls(self):
        result = extract_constraints("fastest route avoiding tolls")
        assert "tolls" in result["avoid"]

    def test_toll_free_phrase(self):
        result = extract_constraints("toll free route please")
        assert "tolls" in result["avoid"]

    def test_avoid_highways(self):
        result = extract_constraints("avoid highways please")
        assert "highways" in result["avoid"]

    def test_last_highway_preference_wins_and_drops_avoid(self):
        result = extract_constraints("avoid highways, prefer highways")
        assert "highways" not in result["avoid"]
        assert "highways" in result["prefer"]
        assert result["contradiction_resolution"] == (
            "Dropped 'avoid highways' because 'prefer highways' was stated later."
        )

    def test_later_non_highway_avoid_does_not_create_contradiction(self):
        result = extract_constraints("prefer highways but avoid tolls")
        assert "highways" in result["prefer"]
        assert "highways" not in result["avoid"]
        assert "tolls" in result["avoid"]
        assert result["contradiction_resolution"] is None

    def test_avoid_highways_alone_is_not_a_contradiction(self):
        result = extract_constraints("avoid highways")
        assert "highways" in result["avoid"]
        assert "highways" not in result["prefer"]
        assert result["contradiction_resolution"] is None

    def test_highway_contradiction_honors_last_avoid_statement(self):
        result = extract_constraints("prefer highways but avoid highways")
        assert "highways" in result["avoid"]
        assert "highways" not in result["prefer"]
        assert result["contradiction_resolution"] == (
            "Dropped 'prefer highways' because 'avoid highways' was stated later."
        )

    def test_dark_roads_avoided_and_lit_preferred(self):
        result = extract_constraints("avoid dark roads at night")
        assert "dark_roads" in result["avoid"]
        assert "lit_roads" in result["prefer"]

    def test_coastal_preference(self):
        result = extract_constraints("scenic route along the coastal ECR road")
        assert "coastal_roads" in result["prefer"]


class TestWaypointParsing:
    def test_single_waypoint_via(self):
        result = extract_constraints("route via tambaram")
        assert "tambaram" in [w.lower() for w in result["waypoints"]]

    def test_multiple_waypoints_and(self):
        result = extract_constraints("fastest route via anna nagar and nungambakkam")
        wps = [w.lower() for w in result["waypoints"]]
        assert "anna nagar" in wps
        assert "nungambakkam" in wps


class TestVehicleType:
    def test_truck_detected(self):
        result = extract_constraints("heavy truck route, avoid narrow roads")
        assert result["vehicle_type"] == "truck"

    def test_bike_detected(self):
        result = extract_constraints("scenic route on my bike")
        assert result["vehicle_type"] == "bike"

    def test_default_vehicle_is_car(self):
        result = extract_constraints("fastest route")
        assert result["vehicle_type"] == "car"


class TestTimeOfDaySafetyBump:
    def test_night_query_raises_safety_weight(self):
        result = extract_constraints("route home at night")
        assert result["weights"]["safety"] >= 0.30
        assert "dark_roads" in result["avoid"]

    def test_explicit_pm_time_parsed(self):
        result = extract_constraints("route at 11pm")
        assert result["time_of_day"] == 23

    def test_explicit_am_time_parsed(self):
        result = extract_constraints("route at 7am")
        assert result["time_of_day"] == 7


class TestTruckConstraintBump:
    def test_truck_prefers_wide_roads_and_avoids_narrow(self):
        result = extract_constraints("truck route")
        assert "wide_roads" in result["prefer"]
        assert "narrow_roads" in result["avoid"]


class TestEmptyQuery:
    def test_empty_query_requests_clarification(self):
        result = extract_constraints("")
        assert result["clarification_needed"] is True
        assert result["clarification_question"]
