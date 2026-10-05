"""Read-only PostGIS queries over the road network and points of interest.

All functions take a SQLAlchemy engine and need PostgreSQL/PostGIS. Every
query pre-filters with a bbox (``&&``) so the GiST indexes are used, then
measures with ``geography`` so distances are real metres.
"""
import json
from typing import Dict, List, Optional

from sqlalchemy import text

from .spatial_store import bbox_from_center

POI_CATEGORIES = (
    "hospital", "clinic", "pharmacy", "school", "college", "university",
    "fuel", "police", "fire_station",
)

_POINT = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
_BOX = "geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)"
_WITHIN = f"ST_DWithin(geom::geography, {_POINT}::geography, :radius_m)"


def _bbox_params(lat: float, lon: float, radius_m: float) -> Dict:
    min_lon, min_lat, max_lon, max_lat = bbox_from_center((lat, lon), radius_m)
    return {
        "lat": lat, "lon": lon, "radius_m": radius_m,
        "min_lon": min_lon, "min_lat": min_lat,
        "max_lon": max_lon, "max_lat": max_lat,
    }


def nearby_pois(
    engine, lat: float, lon: float, radius_m: float,
    category: Optional[str] = None, limit: int = 20,
) -> List[Dict]:
    """POIs within radius_m of a point, nearest first, with real distance."""
    params = _bbox_params(lat, lon, radius_m)
    params["limit"] = limit
    category_filter = ""
    if category:
        category_filter = "AND category = :category"
        params["category"] = category

    query = text(f"""
        SELECT osm_type, osm_id, category, name, attrs,
               ST_Y(geom) AS lat, ST_X(geom) AS lon,
               ST_AsGeoJSON(geom) AS geometry_geojson,
               ST_Distance(geom::geography, {_POINT}::geography) AS distance_m
        FROM osm_pois
        WHERE {_BOX} AND {_WITHIN} {category_filter}
        ORDER BY distance_m
        LIMIT :limit
    """)
    with engine.connect() as connection:
        rows = connection.execute(query, params).mappings().all()
    return [
        {
            "osm_type": row["osm_type"],
            "osm_id": int(row["osm_id"]),
            "category": row["category"],
            "name": row["name"],
            "attrs": _as_dict(row["attrs"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "geometry": json.loads(row["geometry_geojson"]),
            "distance_m": round(float(row["distance_m"]), 1),
        }
        for row in rows
    ]


def adjacent_roads(
    engine, lat: float, lon: float, snap_radius_m: float = 200.0,
) -> Optional[Dict]:
    """Snap a point to its nearest road segment and return the segments that
    touch it (share an endpoint node), i.e. adjacency = zero distance."""
    params = _bbox_params(lat, lon, snap_radius_m)
    snap = text(f"""
        SELECT id, u, v, highway, attrs ->> 'name' AS name, length_m,
               ST_AsGeoJSON(geom) AS geometry_geojson
        FROM osm_edges
        WHERE {_BOX} AND {_WITHIN}
        ORDER BY ST_Distance(geom::geography, {_POINT}::geography)
        LIMIT 1
    """)
    neighbours = text("""
        SELECT DISTINCT ON (e.u, e.v) e.id, e.u, e.v, e.highway,
               e.attrs ->> 'name' AS name, e.length_m,
               ST_AsGeoJSON(e.geom) AS geometry_geojson
        FROM osm_edges AS e
        WHERE e.id <> :edge_id
          AND (e.u IN (:u, :v) OR e.v IN (:u, :v))
        ORDER BY e.u, e.v, e.id
    """)
    with engine.connect() as connection:
        road = connection.execute(snap, params).mappings().first()
        if road is None:
            return None
        adjacent = connection.execute(
            neighbours, {"edge_id": road["id"], "u": road["u"], "v": road["v"]}
        ).mappings().all()
    return {"road": _road(road), "adjacent": [_road(r) for r in adjacent]}


def area_summary(engine, lat: float, lon: float, radius_m: float) -> Dict:
    """Aggregate counts and lengths inside a radius, plus the buffer polygon."""
    params = _bbox_params(lat, lon, radius_m)
    pois = text(f"""
        SELECT category, COUNT(*) AS count FROM osm_pois
        WHERE {_BOX} AND {_WITHIN}
        GROUP BY category ORDER BY count DESC
    """)
    roads = text(f"""
        SELECT highway, COUNT(*) AS segments, SUM(length_m) AS length_m
        FROM osm_edges
        WHERE {_BOX} AND {_WITHIN}
        GROUP BY highway ORDER BY length_m DESC
    """)
    buffer_query = text(
        f"SELECT ST_AsGeoJSON(ST_Buffer({_POINT}::geography, :radius_m)::geometry)"
    )
    with engine.connect() as connection:
        poi_rows = connection.execute(pois, params).mappings().all()
        road_rows = connection.execute(roads, params).mappings().all()
        buffer_geojson = connection.execute(buffer_query, params).scalar_one()
    return {
        "pois": {row["category"]: int(row["count"]) for row in poi_rows},
        "roads": [
            {
                "highway": row["highway"],
                "segments": int(row["segments"]),
                "length_m": round(float(row["length_m"]), 1),
            }
            for row in road_rows
        ],
        "buffer": json.loads(buffer_geojson),
    }


def _road(row) -> Dict:
    return {
        "edge_id": int(row["id"]),
        "u": int(row["u"]),
        "v": int(row["v"]),
        "highway": row["highway"],
        "name": row["name"],
        "length_m": round(float(row["length_m"]), 1),
        "geometry": json.loads(row["geometry_geojson"]),
    }


def _as_dict(value) -> Dict:
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}
