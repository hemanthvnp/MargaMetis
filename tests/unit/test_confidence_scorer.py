"""Unit tests for route_optimizer/confidence_scorer.py::RouteConfidenceScorer."""

import pytest
import networkx as nx

from route_optimizer.confidence_scorer import RouteConfidenceScorer

pytestmark = pytest.mark.unit


class TestScoreBasics:
    def test_empty_route_returns_unknown_risk(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        result = scorer.score([1])  # single node, no edges
        assert result.risk_level == "Unknown"
        assert result.confidence == 50.0

    def test_confidence_within_bounds(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        result = scorer.score([1, 2, 3, 6], departure_hour=14)
        assert 0.0 <= result.confidence <= 100.0

    def test_eta_range_brackets_eta(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        result = scorer.score([1, 2, 3, 6], departure_hour=14)
        best, worst = result.eta_range
        assert best <= result.eta_minutes <= worst


class TestRushHourPenalty:
    def test_morning_rush_hour_scores_lower_than_midday(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        rush = scorer.score([1, 2, 3, 6], departure_hour=8)
        midday = scorer.score([1, 2, 3, 6], departure_hour=13)
        assert rush.breakdown["time_risk"] < midday.breakdown["time_risk"]

    def test_late_night_scores_higher_than_rush_hour(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        night = scorer.score([1, 2, 3, 6], departure_hour=2)
        rush = scorer.score([1, 2, 3, 6], departure_hour=8)
        assert night.breakdown["time_risk"] > rush.breakdown["time_risk"]


class TestRoadQuality:
    def test_motorway_route_scores_higher_quality_than_residential_route(self, small_graph):
        scorer = RouteConfidenceScorer(small_graph)
        motorway_route = scorer.score([1, 2, 3], departure_hour=13)  # primary + motorway
        residential_route = scorer.score([1, 4, 5, 6], departure_hour=13)  # tertiary/residential/secondary
        assert motorway_route.breakdown["road_quality"] > residential_route.breakdown["road_quality"]

    def test_parallel_edges_use_the_shortest_edge_for_confidence(self):
        graph = nx.MultiDiGraph()
        graph.add_edge(1, 2, key=0, length=900.0, highway="primary")
        graph.add_edge(1, 2, key=1, length=120.0, highway="residential")

        edges = RouteConfidenceScorer(graph)._extract_edges([1, 2])

        assert len(edges) == 1
        assert edges[0][2]["length"] == 120.0


class TestRiskLabel:
    @pytest.mark.parametrize("confidence,expected", [(90, "Low"), (60, "Medium"), (20, "High")])
    def test_risk_label_thresholds(self, small_graph, confidence, expected):
        scorer = RouteConfidenceScorer(small_graph)
        assert scorer._risk_label(confidence) == expected
