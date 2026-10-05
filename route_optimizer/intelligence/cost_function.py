from typing import Any, Callable, Dict, List

from route_optimizer.speed_model import (
    ROAD_SPEED_KMPH,
    peak_hour_multiplier,
    parse_road_speed_kmh,
)

ROAD_QUALITY: Dict[str, float] = {
    "motorway": 100.0,
    "motorway_link": 90.0,
    "trunk": 88.0,
    "trunk_link": 80.0,
    "primary": 82.0,
    "primary_link": 75.0,
    "secondary": 70.0,
    "secondary_link": 62.0,
    "tertiary": 55.0,
    "tertiary_link": 48.0,
    "unclassified": 38.0,
    "residential": 30.0,
    "living_street": 20.0,
    "service": 15.0,
    "track": 10.0,
    "path": 5.0,
}

_SAFETY: Dict[str, float] = {
    "motorway": 0.90, "motorway_link": 0.85,
    "trunk": 0.85,    "trunk_link": 0.80,
    "primary": 0.80,  "primary_link": 0.75,
    "secondary": 0.70,"secondary_link": 0.65,
    "tertiary": 0.60, "tertiary_link": 0.55,
    "residential": 0.50, "living_street": 0.55,
    "unclassified": 0.45, "service": 0.35,
    "track": 0.20, "path": 0.15,
}

# Quieter roads score higher for scenic — inverse of safety
_SCENIC: Dict[str, float] = {
    "motorway": 0.05, "motorway_link": 0.05,
    "trunk": 0.10,    "trunk_link": 0.10,
    "primary": 0.20,  "primary_link": 0.20,
    "secondary": 0.35,"secondary_link": 0.35,
    "tertiary": 0.55, "tertiary_link": 0.55,
    "residential": 0.70, "living_street": 0.75,
    "unclassified": 0.85, "service": 0.40,
    "track": 0.80, "path": 0.90,
}

_COMFORT: Dict[str, float] = {
    "motorway": 1.00, "motorway_link": 0.90,
    "trunk": 0.95,    "trunk_link": 0.85,
    "primary": 0.85,  "primary_link": 0.80,
    "secondary": 0.75,"secondary_link": 0.70,
    "tertiary": 0.65, "tertiary_link": 0.60,
    "residential": 0.55, "living_street": 0.60,
    "unclassified": 0.45, "service": 0.40,
    "track": 0.20, "path": 0.15,
}

_FUEL_ACCESS: Dict[str, float] = {
    "motorway": 0.85, "motorway_link": 0.60,
    "trunk": 0.80,    "trunk_link": 0.60,
    "primary": 0.80,  "primary_link": 0.65,
    "secondary": 0.65,"secondary_link": 0.55,
    "tertiary": 0.45, "tertiary_link": 0.40,
    "residential": 0.25, "living_street": 0.20,
    "unclassified": 0.30, "service": 0.35,
    "track": 0.05, "path": 0.05,
}

_DEFAULT_SPEED   = ROAD_SPEED_KMPH.get("unclassified", 40.0)
_DEFAULT_SAFETY  = 0.50
_DEFAULT_SCENIC  = 0.40
_DEFAULT_COMFORT = 0.50
_DEFAULT_FUEL    = 0.50


def _highway(data: Dict) -> str:
    hw = data.get("highway", "unclassified")
    return hw[0] if isinstance(hw, list) else str(hw)


def _parse_speed(data: Dict) -> float:
    return parse_road_speed_kmh(data)


def _is_toll(data: Dict) -> bool:
    return str(data.get("toll", "no")).lower() in ("yes", "true", "1")


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


class CostFunctionGenerator:
    """
    Takes a constraint dict and returns a callable (u, v, edge_data) -> float
    that gets injected directly into the A* traversal.

    All cost components scale with edge length so the algorithm correctly
    trades off a short route on an expensive road type vs a longer detour
    on a cheaper one.
    """

    DIMENSIONS = ("speed", "safety", "fuel_efficiency", "scenic", "comfort", "cost")

    def __init__(self, constraints: Dict[str, Any]) -> None:
        raw = constraints.get("weights", {})
        filled = {d: float(raw.get(d, 0.0)) for d in self.DIMENSIONS}
        self.weights = _normalize_weights(filled)
        self.avoid: List[str] = [a.lower() for a in constraints.get("avoid", [])]
        self.prefer: List[str] = [p.lower() for p in constraints.get("prefer", [])]
        self.time_of_day = constraints.get("time_of_day")

    def generate(self) -> Callable:
        weights = self.weights
        avoid   = self.avoid
        prefer  = self.prefer
        peak_multiplier = peak_hour_multiplier(self.time_of_day)

        def cost_fn(u: int, v: int, data: Dict) -> float:
            length = float(data.get("length", 1.0))
            hw = _highway(data)

            # Hard penalties for avoided road types
            if "tolls" in avoid and _is_toll(data):
                return length * 1000.0
            if "highways" in avoid and hw in ("motorway", "motorway_link", "trunk", "trunk_link"):
                return length * 500.0
            if "unpaved" in avoid and hw in ("track", "path"):
                return length * 200.0
            if "narrow_roads" in avoid and hw in ("residential", "living_street", "service"):
                return length * 3.0
            if "busy_roads" in avoid and hw in ("motorway", "trunk", "primary"):
                return length * 4.0
            if "dark_roads" in avoid and hw in ("unclassified", "track", "path"):
                return length * 3.0

            # Discount for preferred road types
            prefer_mult = 1.0
            if "highways" in prefer and hw in ("motorway", "trunk", "primary"):
                prefer_mult *= 0.85
            if "scenic_roads" in prefer and hw in ("unclassified", "residential", "tertiary"):
                prefer_mult *= 0.85
            if "fuel_stations" in prefer and hw in ("motorway", "trunk", "primary", "secondary"):
                prefer_mult *= 0.90
            if "lit_roads" in prefer and hw in ("motorway", "trunk", "primary", "secondary"):
                prefer_mult *= 0.90
            if "wide_roads" in prefer and hw in ("motorway", "trunk", "primary"):
                prefer_mult *= 0.85

            # Speed: time to traverse in seconds, scaled back to metre-equivalent
            speed_ms = _parse_speed(data) / 3.6
            speed_component = (length / speed_ms if speed_ms > 0 else length * 10.0) * 40.0
            safety_component  = (1.0 - _SAFETY.get(hw, _DEFAULT_SAFETY)) * length

            # Fuel is least efficient at extremes of speed — penalise deviation from ~80 km/h
            eff_speed = _parse_speed(data)
            fuel_component = (1.0 + abs(eff_speed - 80.0) / 80.0) * length

            scenic_component  = (1.0 - _SCENIC.get(hw, _DEFAULT_SCENIC)) * length
            comfort_component = (1.0 - _COMFORT.get(hw, _DEFAULT_COMFORT)) * length
            cost_component    = (length * 2.0 if _is_toll(data) else 0.0) + length * 0.1

            turn_penalty = 0.0
            if data.get("junction") in {"roundabout", "traffic_signals", "signal"}:
                turn_penalty += length * 0.12
            if hw in {"residential", "unclassified", "service", "living_street"} and data.get("lanes"):
                try:
                    lanes = float(str(data.get("lanes")).split(";")[0])
                    if lanes <= 2:
                        turn_penalty += length * 0.08
                except (TypeError, ValueError):
                    pass

            total = (
                weights["speed"]           * speed_component * peak_multiplier
                + weights["safety"]        * safety_component
                + weights["fuel_efficiency"]* fuel_component
                + weights["scenic"]        * scenic_component
                + weights["comfort"]       * comfort_component
                + weights["cost"]          * cost_component
                + 0.5 * weights["comfort"] * turn_penalty
            )
            return total * prefer_mult

        return cost_fn

    def describe(self) -> str:
        parts = [f"{d}={w:.2f}" for d, w in self.weights.items() if w > 0.01]
        return "cost = " + " + ".join(parts)
