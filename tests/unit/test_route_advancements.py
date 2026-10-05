from route_optimizer.intelligence.constraint_engine import extract_constraints
from route_optimizer.intelligence.cost_function import CostFunctionGenerator
from route_optimizer.intelligence.route_ranker import RouteRanker
from route_optimizer.optimizer import RouteOptimizer
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
    assert CostFunctionGenerator(morning).generate()(1, 2, edge) > CostFunctionGenerator(off_peak).generate()(1, 2, edge)


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
        time_of_day=12,
    )
    smart_route_eta = _route_eta_minutes(
        small_graph, {"path": result["path"]}, time_of_day=12
    )

    assert result["estimated_time_min"] == round(smart_route_eta, 2)
