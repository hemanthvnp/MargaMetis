"""
confidence_scorer.py
--------------------
MārgaMetis — Route Confidence Scorer
Contribution by: [Your Name]

What this does:
  Given a route (list of edges from OSMnx graph), this module scores
  how RELIABLE that route is — not just how fast.

  Three sub-scores are combined:
    1. Speed Consistency Score  — does road speed vary wildly along the route?
    2. Road Quality Score       — are these major roads or sketchy back lanes?
    3. Time-of-Day Risk Score   — is this a rush-hour route?

  Final confidence = weighted average of all three (0–100%).

Why it impresses:
  - Directly maps to "Quantitative Risk Engine" concept from the project plan
  - Inspired by Sharpe ratio (reward / risk) from finance → applied to routing
  - Each route now has a confidence interval, not just a single ETA number
  - Zero external API needed — works entirely from OSMnx graph attributes

Usage:
  from route_optimizer.confidence_scorer import RouteConfidenceScorer

  scorer = RouteConfidenceScorer(graph)
  result = scorer.score(route_edges, departure_hour=8)
  print(result)
  # {
  #   'confidence': 73.4,
  #   'eta_minutes': 42,
  #   'eta_range': (38, 51),        # best case / worst case
  #   'risk_level': 'Medium',
  #   'breakdown': {
  #       'speed_consistency': 81.2,
  #       'road_quality': 79.0,
  #       'time_risk': 58.0
  #   },
  #   'warnings': ['Rush hour detected', '2 residential roads on route']
  # }
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from route_optimizer.intelligence.cost_function import ROAD_QUALITY


# ─────────────────────────────────────────────
# Data class for a clean result object
# ─────────────────────────────────────────────

@dataclass
class ConfidenceResult:
    confidence: float           # 0–100, higher = more reliable
    eta_minutes: float          # expected travel time
    eta_range: tuple            # (optimistic_minutes, pessimistic_minutes)
    risk_level: str             # 'Low' / 'Medium' / 'High'
    breakdown: dict             # sub-scores
    warnings: list = field(default_factory=list)

    def __str__(self):
        return (
            f"Confidence: {self.confidence:.1f}%  |  "
            f"Risk: {self.risk_level}  |  "
            f"ETA: {self.eta_minutes:.0f} min "
            f"(best {self.eta_range[0]:.0f} – worst {self.eta_range[1]:.0f})\n"
            f"Breakdown → Speed: {self.breakdown['speed_consistency']:.0f}%  "
            f"Roads: {self.breakdown['road_quality']:.0f}%  "
            f"Time-risk: {self.breakdown['time_risk']:.0f}%\n"
            f"Warnings: {', '.join(self.warnings) if self.warnings else 'None'}"
        )


# Rush hours — confidence penalty applies
RUSH_HOUR_MORNING = range(7, 10)   # 7am–9am
RUSH_HOUR_EVENING = range(17, 20)  # 5pm–7pm

# Weights for final score (must sum to 1.0)
WEIGHTS = {
    'speed_consistency': 0.40,
    'road_quality':      0.35,
    'time_risk':         0.25,
}


# ─────────────────────────────────────────────
# Main scorer class
# ─────────────────────────────────────────────

class RouteConfidenceScorer:
    """
    Scores how reliable a given route is.

    Parameters
    ----------
    graph : networkx.MultiDiGraph
        The OSMnx road network graph for the city.
    """

    def __init__(self, graph):
        self.graph = graph

    # ── public entry point ──────────────────

    def score(
        self,
        route_nodes: list,
        departure_hour: int = 12,
        avg_speed_kmh: float = 40.0,
    ) -> ConfidenceResult:
        """
        Score a route's reliability.

        Parameters
        ----------
        route_nodes : list of int
            Ordered list of OSMnx node IDs (the path A* returned).
        departure_hour : int
            Hour of departure in 24h format (0–23). Default noon.
        avg_speed_kmh : float
            Baseline average speed for ETA calculation.

        Returns
        -------
        ConfidenceResult
        """
        edges = self._extract_edges(route_nodes)

        if not edges:
            # Fallback for empty / single-node route
            return ConfidenceResult(
                confidence=50.0,
                eta_minutes=0,
                eta_range=(0, 0),
                risk_level='Unknown',
                breakdown={
                    'speed_consistency': 50.0,
                    'road_quality': 50.0,
                    'time_risk': 50.0,
                },
                warnings=['Could not extract route edges'],
            )

        speed_score = self._speed_consistency_score(edges)
        quality_score = self._road_quality_score(edges)
        time_score = self._time_of_day_score(departure_hour)

        # Weighted final confidence
        confidence = (
            speed_score  * WEIGHTS['speed_consistency'] +
            quality_score * WEIGHTS['road_quality'] +
            time_score   * WEIGHTS['time_risk']
        )
        confidence = round(min(max(confidence, 0), 100), 1)

        # ETA with uncertainty range
        total_length_km = sum(self._edge_length(e) for e in edges)
        eta = (total_length_km / avg_speed_kmh) * 60  # minutes

        # Uncertainty grows as confidence falls
        # At 100% confidence → ±5%
        # At   0% confidence → ±40%
        uncertainty = 0.05 + (1 - confidence / 100) * 0.35
        eta_best  = eta * (1 - uncertainty * 0.5)
        eta_worst = eta * (1 + uncertainty)

        warnings = self._generate_warnings(
            edges, departure_hour, speed_score, quality_score
        )

        risk_level = self._risk_label(confidence)

        return ConfidenceResult(
            confidence=confidence,
            eta_minutes=round(eta, 1),
            eta_range=(round(eta_best, 1), round(eta_worst, 1)),
            risk_level=risk_level,
            breakdown={
                'speed_consistency': round(speed_score, 1),
                'road_quality':      round(quality_score, 1),
                'time_risk':         round(time_score, 1),
            },
            warnings=warnings,
        )

    # ── sub-scorers ─────────────────────────

    def _speed_consistency_score(self, edges: list) -> float:
        """
        How consistent are the speed limits along this route?

        A route with uniform 60 km/h is more predictable than one that
        jumps 30 → 80 → 20 → 60. High variance = low confidence.

        Inspired by: coefficient of variation (CV) in statistics.
        Lower CV → higher score.
        """
        speeds = []
        for u, v, data in edges:
            raw = data.get('maxspeed', None)
            speed = self._parse_speed(raw)
            if speed:
                speeds.append(speed)

        if len(speeds) < 2:
            return 65.0  # not enough data → neutral score

        mean_speed = statistics.mean(speeds)
        stdev_speed = statistics.stdev(speeds)

        if mean_speed == 0:
            return 50.0

        cv = stdev_speed / mean_speed  # 0 = perfectly uniform, >1 = very uneven

        # Map CV to score: CV=0 → 100, CV=1 → 0  (linear)
        score = max(0.0, 100.0 - cv * 100.0)
        return score

    def _road_quality_score(self, edges: list) -> float:
        """
        What types of roads does this route use?

        A route on motorways and primary roads is more reliable than
        one through residential and service roads.
        """
        quality_values = []
        for u, v, data in edges:
            highway = data.get('highway', 'unclassified')
            # highway can be a list in OSMnx (multiple tags)
            if isinstance(highway, list):
                highway = highway[0]
            quality = ROAD_QUALITY.get(str(highway), 35)
            quality_values.append(quality)

        if not quality_values:
            return 50.0

        return statistics.mean(quality_values)

    def _time_of_day_score(self, departure_hour: int) -> float:
        """
        Is this departure time during rush hour?

        Rush hour = lower confidence because speed predictions
        are less reliable when traffic is heavy and unpredictable.
        """
        if departure_hour in RUSH_HOUR_MORNING:
            # Peak morning rush → significant penalty
            return 45.0
        if departure_hour in RUSH_HOUR_EVENING:
            # Peak evening rush → moderate penalty
            return 50.0
        if 0 <= departure_hour <= 5:
            # Late night / early morning → very predictable
            return 95.0
        if 10 <= departure_hour <= 15:
            # Mid-day → fairly predictable
            return 82.0
        # Shoulder times (6am, 7pm–midnight)
        return 68.0

    # ── helpers ─────────────────────────────

    def _extract_edges(self, route_nodes: list) -> list:
        """Convert list of node IDs into list of (u, v, data) edge tuples."""
        edges = []
        for i in range(len(route_nodes) - 1):
            u = route_nodes[i]
            v = route_nodes[i + 1]
            edge_data = self.graph.get_edge_data(u, v)
            if edge_data:
                data = min(edge_data.values(), key=lambda d: float(d.get("length", float("inf"))))
                edges.append((u, v, data))
        return edges

    def _edge_length(self, edge: tuple) -> float:
        """Return edge length in km."""
        _, _, data = edge
        length_m = data.get('length', 0)
        return length_m / 1000.0

    def _parse_speed(self, raw) -> Optional[float]:
        """
        Parse OSMnx maxspeed field → float km/h.
        Handles: '50', '50 mph', ['50', '60'], None.
        """
        if raw is None:
            return None
        if isinstance(raw, list):
            raw = raw[0]
        raw = str(raw).strip().lower()
        if 'mph' in raw:
            try:
                return float(raw.replace('mph', '').strip()) * 1.60934
            except ValueError:
                return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _risk_label(self, confidence: float) -> str:
        """Convert numeric confidence to human-readable risk level."""
        if confidence >= 75:
            return 'Low'
        if confidence >= 50:
            return 'Medium'
        return 'High'

    def _generate_warnings(
        self,
        edges: list,
        departure_hour: int,
        speed_score: float,
        quality_score: float,
    ) -> list:
        """Generate plain-English warnings for the UI to display."""
        warnings = []

        if departure_hour in RUSH_HOUR_MORNING:
            warnings.append('Morning rush hour — expect delays')
        elif departure_hour in RUSH_HOUR_EVENING:
            warnings.append('Evening rush hour — expect delays')

        # Count road types
        residential_count = sum(
            1 for _, _, d in edges
            if str(d.get('highway', '')).startswith('residential')
               or str(d.get('highway', '')).startswith('living')
        )
        if residential_count > 3:
            warnings.append(
                f'{residential_count} residential roads — slower and less predictable'
            )

        if speed_score < 50:
            warnings.append('High speed variation — ETA estimate less reliable')

        if quality_score < 40:
            warnings.append('Route uses low-quality roads')

        # Check for missing speed data
        missing_speed = sum(
            1 for _, _, d in edges if d.get('maxspeed') is None
        )
        if missing_speed > len(edges) * 0.5:
            warnings.append('Speed data missing for >50% of route')

        return warnings


# ─────────────────────────────────────────────
# Standalone demo — run this file directly to test
# python confidence_scorer.py
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("MārgaMetis — Route Confidence Scorer demo")
    print("=" * 50)

    # We mock a small graph here so you can run without OSMnx
    import networkx as nx

    G = nx.MultiDiGraph()

    # Add some fake nodes (node_id → lat/lon)
    nodes = {
        1: {'x': 80.2707, 'y': 13.0827},
        2: {'x': 80.2750, 'y': 13.0860},
        3: {'x': 80.2800, 'y': 13.0900},
        4: {'x': 80.2850, 'y': 13.0930},
        5: {'x': 80.2900, 'y': 13.0970},
    }
    for nid, attrs in nodes.items():
        G.add_node(nid, **attrs)

    # Add edges with realistic OSMnx-style attributes
    G.add_edge(1, 2, length=450, highway='primary',     maxspeed='60')
    G.add_edge(2, 3, length=600, highway='primary',     maxspeed='60')
    G.add_edge(3, 4, length=300, highway='residential', maxspeed='30')
    G.add_edge(4, 5, length=500, highway='secondary',   maxspeed='50')

    scorer = RouteConfidenceScorer(G)

    route_a = [1, 2, 3, 4, 5]   # mixed roads
    route_b = [1, 2, 3]          # all primary

    print("\nRoute A (mixed roads, 8am departure):")
    print(scorer.score(route_a, departure_hour=8))

    print("\nRoute A (mixed roads, 2pm departure):")
    print(scorer.score(route_a, departure_hour=14))

    print("\nRoute B (primary roads only, 2pm departure):")
    print(scorer.score(route_b, departure_hour=14))

    print("\nRoute B (primary roads only, 8am rush hour):")
    print(scorer.score(route_b, departure_hour=8))