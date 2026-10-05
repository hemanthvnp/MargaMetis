from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

AVG_SPEED_KMPH = {
    "car": 40,
    "bike": 25,
    "bus": 30,
    "truck": 25,
    "auto": 35,
}

ROAD_SPEED_KMPH: Dict[str, float] = {
    "motorway": 100.0,
    "motorway_link": 80.0,
    "trunk": 80.0,
    "trunk_link": 60.0,
    "primary": 60.0,
    "primary_link": 50.0,
    "secondary": 50.0,
    "secondary_link": 40.0,
    "tertiary": 40.0,
    "tertiary_link": 30.0,
    "residential": 30.0,
    "living_street": 20.0,
    "unclassified": 40.0,
    "service": 20.0,
    "track": 15.0,
    "path": 10.0,
}


def _highway_name(data: Dict) -> str:
    highway = data.get("highway", "unclassified")
    if isinstance(highway, list):
        return str(highway[0])
    return str(highway)


def parse_road_speed_kmh(data: Dict) -> float:
    raw = data.get("maxspeed")
    if raw is not None:
        if isinstance(raw, list):
            raw = raw[0]
        try:
            value = str(raw).strip().lower().replace(" kph", "").replace(" km/h", "").replace(" mph", "")
            if "mph" in str(raw).lower():
                return float(value) * 1.609344
            return float(value)
        except (TypeError, ValueError):
            pass
    return ROAD_SPEED_KMPH.get(_highway_name(data), 40.0)


def peak_hour_multiplier(hour: Optional[int]) -> float:
    if hour is None:
        return 1.0
    hour = int(hour) % 24
    if hour in {7, 8, 9, 17, 18, 19, 20}:
        return 1.30
    if 10 <= hour <= 16:
        return 1.10
    if 0 <= hour <= 5:
        return 0.92
    return 1.0


def estimate_eta_minutes(distance_m: float, speed_kmh: float) -> float:
    if speed_kmh <= 0:
        return 0.0
    return (distance_m / 1000.0) / speed_kmh * 60.0


def estimate_path_eta_minutes(graph, path, time_of_day: Optional[int] = None) -> float:
    """Estimate ETA using the same OSM edge speeds used by route costs."""
    total_minutes = 0.0
    for u, v in zip(path, path[1:]):
        edges = graph.get_edge_data(u, v)
        if not edges:
            raise ValueError(f"Route path contains missing edge {u}->{v}")
        edge = min(edges.values(), key=lambda data: float(data.get("length", float("inf"))))
        length_m = float(edge.get("length", 0.0))
        total_minutes += estimate_eta_minutes(length_m, parse_road_speed_kmh(edge))
    return total_minutes * peak_hour_multiplier(time_of_day)


def vehicle_speed_kmh(vehicle_type: str) -> float:
    return float(AVG_SPEED_KMPH.get(str(vehicle_type).lower(), 40))
