"""Unit tests for route_optimizer/intelligence/route_ranker.py::RouteRanker."""

import pytest

from route_optimizer.intelligence.route_ranker import RouteRanker

pytestmark = pytest.mark.unit


def _routes(small_graph):
    # "distance" mirrors what GraphEngine.astar()/dijkstra() actually return
    # alongside "path" -- RouteRanker._deduplicate() keys off top-level
    # "distance", not the per-route "scores.total_length_m" computed later.
    return [
        {"path": [1, 2, 3], "distance": 2000.0},        # primary + motorway (fast, toll)
        {"path": [1, 4, 5, 6], "distance": 3100.0},      # tertiary/residential/secondary (scenic-ish, toll-free)
    ]


class TestRankRoutes:
    def test_empty_input_returns_empty(self, small_graph):
        ranker = RouteRanker(small_graph)
        assert ranker.rank_routes([]) == []

    def test_every_route_gets_scores_and_rank(self, small_graph):
        ranker = RouteRanker(small_graph)
        ranked = ranker.rank_routes(_routes(small_graph))
        for r in ranked:
            assert "scores" in r
            assert "rank" in r
            assert "label" in r
            assert "explanation" in r

    def test_ranks_are_sequential_starting_at_one(self, small_graph):
        ranker = RouteRanker(small_graph)
        ranked = ranker.rank_routes(_routes(small_graph))
        assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))

    def test_sorted_by_descending_composite_score(self, small_graph):
        ranker = RouteRanker(small_graph)
        ranked = ranker.rank_routes(_routes(small_graph))
        composites = [r["scores"]["composite"] for r in ranked]
        assert composites == sorted(composites, reverse=True)

    def test_toll_route_has_lower_toll_cost_score(self, small_graph):
        ranker = RouteRanker(small_graph)
        ranked = ranker.rank_routes(_routes(small_graph))
        by_path = {tuple(r["path"]): r for r in ranked}
        toll_route = by_path[(1, 2, 3)]
        free_route = by_path[(1, 4, 5, 6)]
        assert toll_route["scores"]["toll_free"] is False
        assert free_route["scores"]["toll_free"] is True
        assert toll_route["scores"]["toll_cost"] < free_route["scores"]["toll_cost"]

    def test_speed_weighted_constraints_favour_faster_route_label(self, small_graph):
        ranker = RouteRanker(small_graph)
        constraints = {"weights": {"speed": 1.0, "safety": 0.0, "fuel_efficiency": 0.0,
                                    "scenic": 0.0, "comfort": 0.0, "cost": 0.0}}
        ranked = ranker.rank_routes(_routes(small_graph), constraints)
        labels = [r["label"] for r in ranked]
        assert "Fastest" in labels


class TestDeduplication:
    def test_near_identical_routes_are_deduplicated(self, small_graph):
        ranker = RouteRanker(small_graph)
        routes = [{"path": [1, 2, 3], "distance": 2000.0}, {"path": [1, 2, 3], "distance": 2000.0}]
        ranked = ranker.rank_routes(routes)
        assert len(ranked) == 1

    def test_edge_jaccard_deduplicates_routes_above_seventy_percent(self):
        routes = [
            {
                "path": [1, 2, 3, 4],
                "distance": 1000,
                "scores": {"composite": 0.2},
            },
            {
                "path": [1, 2, 3, 4, 5],
                "distance": 5000,
                "scores": {"composite": 0.9},
            },
            {
                "path": [7, 8, 9, 10],
                "distance": 5000,
                "scores": {"composite": 0.3},
            },
        ]

        deduplicated = RouteRanker._deduplicate(routes)

        assert [route["path"] for route in deduplicated] == [
            [1, 2, 3, 4],
            [7, 8, 9, 10],
        ]
