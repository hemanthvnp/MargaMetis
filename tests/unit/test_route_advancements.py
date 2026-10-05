import pytest

from route_optimizer.intelligence.constraint_engine import extract_constraints
from route_optimizer.intelligence.cost_function import CostFunctionGenerator
from route_optimizer.intelligence.route_ranker import RouteRanker
from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.speed_model import estimate_path_eta_minutes
from app.routes.route_api import _route_eta_minutes


def test_extract_constraints_flags_contradiction():
    constraints = extract_constraints("avoid highways but prefer highways for a fast scenic route")
    assert constraints["contradiction_resolution"] is not None
    assert "highway" in constraints["contradiction_resolution"].lower()


def test_cost_function_applies_peak_hour_penalty():
    morning = {
        "weights": {"speed": 1.0, "safety": 0.0, "fuel_efficiency": 0.0, "scenic": 0.0, "comfort": 0.0, "cost": 0.0},
        "avoid": [],
        "prefer": [],
        "time_of_day": 18,
    }
    off_peak = {
        "weights": {"speed": 1.0, "safety": 0.0, "fuel_efficiency": 0.0, "scenic": 0.0, "comfort": 0.0, "cost": 0.0},
        "avoid": [],
        "prefer": [],
        "time_of_day": 3,
    }
    edge = {"length": 1000.0, "highway": "motorway", "maxspeed": "60"}
    peak_cost = CostFunctionGenerator(morning).generate()(1, 2, edge)
    off_peak_cost = CostFunctionGenerator(off_peak).generate()(1, 2, edge)
    base_cost = CostFunctionGenerator({**morning, "time_of_day": None}).generate()(1, 2, edge)
    assert peak_cost == pytest.approx(base_cost * 1.30)
    assert off_peak_cost == pytest.approx(base_cost * 0.92)


def test_peak_multiplier_is_applied_once_to_final_eta(tiny_graph):
    base_eta = estimate_path_eta_minutes(tiny_graph, [1, 2, 3])
    peak_eta = estimate_path_eta_minutes(tiny_graph, [1, 2, 3], time_of_day=18)
    off_peak_eta = estimate_path_eta_minutes(tiny_graph, [1, 2, 3], time_of_day=3)

    assert peak_eta == pytest.approx(base_eta * 1.30)
    assert off_peak_eta == pytest.approx(base_eta * 0.92)


def test_route_ranker_deduplicates_overlapping_paths():
    routes = [
        {"path": [10, 11, 12, 13], "distance": 1000, "scores": {"composite": 0.81}},
        {"path": [10, 11, 12, 13], "distance": 1010, "scores": {"composite": 0.80}},
    ]
    assert len(RouteRanker._deduplicate(routes)) == 1


def test_optimizer_and_smart_route_share_per_edge_eta(small_graph):
    optimizer = RouteOptimizer()
    optimizer.graph = small_graph

    result = optimizer.find_route(
        (small_graph.nodes[1]["y"], small_graph.nodes[1]["x"]),
        (small_graph.nodes[3]["y"], small_graph.nodes[3]["x"]),
        time_of_day=18,
    )
    smart_route_eta = _route_eta_minutes(
        small_graph, {"path": result["path"]}, time_of_day=18
    )

    assert result["estimated_time_min"] == round(smart_route_eta, 2)
