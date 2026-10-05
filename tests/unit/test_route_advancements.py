import pytest
import networkx as nx

from route_optimizer.intelligence.constraint_engine import extract_constraints
from route_optimizer.intelligence.cost_function import (
    ROAD_QUALITY,
    CostFunctionGenerator,
    _safety_score,
    _turn_angle_degrees,
)
from route_optimizer.intelligence.graph_engine import GraphEngine
from route_optimizer.intelligence.route_ranker import RouteRanker
from route_optimizer.confidence_scorer import RouteConfidenceScorer
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


@pytest.mark.parametrize(("highway", "quality"), ROAD_QUALITY.items())
def test_safety_score_uses_road_quality(highway, quality):
    edge = {"length": 100.0, "highway": highway}
    safety_cost = CostFunctionGenerator({
        "weights": {"safety": 1.0},
    }).generate()(1, 2, edge)

    assert _safety_score(highway) == quality / 100.0
    assert safety_cost == pytest.approx((1 - quality / 100.0) * 100.0)
    assert RouteConfidenceScorer(None)._road_quality_score([(1, 2, edge)]) == quality


def test_unknown_highway_safety_uses_quality_default():
    assert _safety_score("unknown") == 0.5


def test_bearing_turn_cost_prefers_equal_length_path_with_fewer_turns():
    graph = nx.MultiDiGraph()
    coords = {
        1: (0.0, 0.0),
        2: (0.0, 0.0001),
        3: (0.0, 0.0002),
        4: (0.0001, 0.0),
        5: (0.0, 0.0003),
        6: (0.0001, 0.0002),
    }
    for node, (lat, lon) in coords.items():
        graph.add_node(node, y=lat, x=lon)
    edge_data = {"length": 100.0, "highway": "residential", "maxspeed": "30"}
    for u, v in (
        (1, 2), (2, 3), (3, 5),
        (1, 4), (4, 6), (6, 5),
    ):
        graph.add_edge(u, v, **edge_data)

    straight_path = [1, 2, 3, 5]
    turning_path = [1, 4, 6, 5]
    cost_fn = CostFunctionGenerator({"weights": {"comfort": 1.0}}).generate(graph)

    def path_cost(path):
        return sum(
            cost_fn(
                u,
                v,
                graph.get_edge_data(u, v)[0],
                path[index - 1] if index > 0 else None,
            )
            for index, (u, v) in enumerate(zip(path, path[1:]))
        )

    assert path_cost(straight_path) < path_cost(turning_path)
    assert GraphEngine(graph).astar(1, 5, cost_fn)["path"] == straight_path


def test_bearing_turn_angles_scale_from_straight_to_uturn():
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=0.0, x=0.0)
    graph.add_node(2, y=0.0, x=0.001)
    graph.add_node(3, y=0.0, x=0.002)
    graph.add_node(4, y=-0.001, x=0.001)

    assert _turn_angle_degrees(graph, 1, 2, 3) == pytest.approx(0.0)
    assert _turn_angle_degrees(graph, 1, 2, 4) == pytest.approx(90.0)
    assert _turn_angle_degrees(graph, 1, 2, 1) == pytest.approx(180.0)
