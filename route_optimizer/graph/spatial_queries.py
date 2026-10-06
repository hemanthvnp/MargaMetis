"""Read-only PostGIS queries over the road network and points of interest.

All functions take a SQLAlchemy engine and need PostgreSQL/PostGIS. Every
query pre-filters with a bbox (``&&``) so the GiST indexes are used, then
measures with ``geography`` so distances are real metres.
"""
import json
from typing import Dict, List, Optional, Sequence, Tuple

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


def places_along_route(
    engine, path_lonlat: Sequence[Tuple[float, float]], distance_m: float,
    category: Optional[str] = None, limit: int = 100,
) -> List[Dict]:
    """POIs within distance_m of a route line, in travel order.

    path_lonlat is the route as (lon, lat) pairs. along_m is how far along the
    route the place's closest point is; distance_from_route_m is the detour.
    """
    wkt_line = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in path_lonlat) + ")"
    pad_deg = distance_m / 111_320.0 * 1.5  # bbox pre-filter for the GiST index
    params = {"wkt": wkt_line, "distance_m": distance_m, "pad": pad_deg, "limit": limit}
    category_filter = ""
    if category:
        category_filter = "AND p.category = :category"
        params["category"] = category

    query = text(f"""
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromText(CAST(:wkt AS TEXT)), 4326) AS geom
        )
        SELECT p.osm_type, p.osm_id, p.category, p.name, p.attrs,
               ST_Y(p.geom) AS lat, ST_X(p.geom) AS lon,
               ST_Distance(p.geom::geography, route.geom::geography) AS distance_from_route_m,
               ST_LineLocatePoint(route.geom, p.geom)
                   * ST_Length(route.geom::geography) AS along_m
        FROM osm_pois AS p, route
        WHERE p.geom && ST_Expand(route.geom, :pad)
          AND ST_DWithin(p.geom::geography, route.geom::geography, :distance_m)
          {category_filter}
        ORDER BY along_m
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
            "distance_from_route_m": round(float(row["distance_from_route_m"]), 1),
            "along_m": round(float(row["along_m"]), 1),
        }
        for row in rows
    ]


def _polygon_wkt(ring_lonlat: Sequence[Tuple[float, float]]) -> str:
    ring = list(ring_lonlat)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in ring) + "))"


def places_in_area(
    engine, ring_lonlat: Sequence[Tuple[float, float]],
    category: Optional[str] = None, limit: int = 200,
) -> Optional[Dict]:
    """POIs inside a polygon (containment), with the polygon's area, centroid,
    per-category counts and the most central place (closest to the centroid).

    Returns None when the polygon is invalid (e.g. it crosses itself).
    """
    params = {"wkt": _polygon_wkt(ring_lonlat), "limit": limit}
    category_filter = ""
    if category:
        category_filter = "AND p.category = :category"
        params["category"] = category

    poly = "ST_SetSRID(ST_GeomFromText(CAST(:wkt AS TEXT)), 4326)"
    meta = text(f"""
        SELECT ST_IsValid({poly}) AS valid,
               ST_Area({poly}::geography) AS area_m2,
               ST_Y(ST_Centroid({poly})) AS lat, ST_X(ST_Centroid({poly})) AS lon
    """)
    items_query = text(f"""
        WITH poly AS (SELECT {poly} AS geom)
        SELECT p.osm_type, p.osm_id, p.category, p.name, p.attrs,
               ST_Y(p.geom) AS lat, ST_X(p.geom) AS lon,
               ST_Distance(p.geom::geography, ST_Centroid(poly.geom)::geography)
                   AS distance_to_centroid_m
        FROM osm_pois AS p, poly
        WHERE p.geom && poly.geom AND ST_Within(p.geom, poly.geom) {category_filter}
        ORDER BY distance_to_centroid_m
        LIMIT :limit
    """)
    counts_query = text(f"""
        WITH poly AS (SELECT {poly} AS geom)
        SELECT p.category, COUNT(*) AS count
        FROM osm_pois AS p, poly
        WHERE p.geom && poly.geom AND ST_Within(p.geom, poly.geom) {category_filter}
        GROUP BY p.category ORDER BY count DESC
    """)
    with engine.connect() as connection:
        info = connection.execute(meta, params).mappings().one()
        if not info["valid"]:
            return None
        rows = connection.execute(items_query, params).mappings().all()
        counts = connection.execute(counts_query, params).mappings().all()
    items = [
        {
            "osm_type": row["osm_type"],
            "osm_id": int(row["osm_id"]),
            "category": row["category"],
            "name": row["name"],
            "attrs": _as_dict(row["attrs"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "distance_to_centroid_m": round(float(row["distance_to_centroid_m"]), 1),
        }
        for row in rows
    ]
    return {
        "area_km2": round(float(info["area_m2"]) / 1e6, 3),
        "centroid": {"lat": float(info["lat"]), "lon": float(info["lon"])},
        "counts": {row["category"]: int(row["count"]) for row in counts},
        "most_central": items[0] if items else None,
        "items": items,
    }


def compare_areas(engine, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Dict:
    """Overlay two circles, each (lat, lon, radius_m): union, intersection and
    symmetric difference, with areas in km2 and the shapes as GeoJSON."""
    params = {
        "alat": a[0], "alon": a[1], "ar": a[2],
        "blat": b[0], "blon": b[1], "br": b[2],
    }
    query = text("""
        WITH a AS (
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(:alon, :alat), 4326)::geography, :ar)::geometry AS g
        ), b AS (
            SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(:blon, :blat), 4326)::geography, :br)::geometry AS g
        )
        SELECT ST_Area(a.g::geography) AS area_a,
               ST_Area(b.g::geography) AS area_b,
               ST_Area(ST_Union(a.g, b.g)::geography) AS area_union,
               ST_Area(ST_Intersection(a.g, b.g)::geography) AS area_intersection,
               ST_Area(ST_SymDifference(a.g, b.g)::geography) AS area_sym_difference,
               ST_AsGeoJSON(a.g) AS a_geojson, ST_AsGeoJSON(b.g) AS b_geojson,
               ST_AsGeoJSON(ST_Union(a.g, b.g)) AS union_geojson,
               ST_AsGeoJSON(ST_Intersection(a.g, b.g)) AS intersection_geojson
        FROM a, b
    """)
    with engine.connect() as connection:
        row = connection.execute(query, params).mappings().one()
    km2 = lambda value: round(float(value) / 1e6, 3)  # noqa: E731
    smaller = min(float(row["area_a"]), float(row["area_b"]))
    return {
        "area_km2": {
            "a": km2(row["area_a"]), "b": km2(row["area_b"]),
            "union": km2(row["area_union"]),
            "intersection": km2(row["area_intersection"]),
            "symmetric_difference": km2(row["area_sym_difference"]),
        },
        "overlap_pct_of_smaller": round(
            100.0 * float(row["area_intersection"]) / smaller, 1) if smaller else 0.0,
        "a": json.loads(row["a_geojson"]),
        "b": json.loads(row["b_geojson"]),
        "union": json.loads(row["union_geojson"]),
        "intersection": json.loads(row["intersection_geojson"]),
    }


def nearest_place_to_each(
    engine, points: Sequence[Tuple[float, float]], category: Optional[str] = None,
) -> List[Dict]:
    """k-NN join: for every (lat, lon) point, its single nearest place.

    The LATERAL subquery orders by the geometry <-> operator, which the GiST
    index answers directly; distance is then measured in metres.
    """
    params = {
        "idx": list(range(len(points))),
        "lats": [lat for lat, _ in points],
        "lons": [lon for _, lon in points],
    }
    category_filter = ""
    if category:
        category_filter = "WHERE p.category = :category"
        params["category"] = category

    query = text(f"""
        SELECT pt.idx, pt.lat AS from_lat, pt.lon AS from_lon,
               n.osm_type, n.osm_id, n.category, n.name,
               ST_Y(n.geom) AS lat, ST_X(n.geom) AS lon,
               ST_Distance(n.geom::geography,
                           ST_SetSRID(ST_MakePoint(pt.lon, pt.lat), 4326)::geography) AS distance_m
        FROM unnest(CAST(:idx AS INT[]), CAST(:lats AS FLOAT8[]), CAST(:lons AS FLOAT8[]))
             AS pt(idx, lat, lon)
        CROSS JOIN LATERAL (
            SELECT p.* FROM osm_pois AS p
            {category_filter}
            ORDER BY p.geom <-> ST_SetSRID(ST_MakePoint(pt.lon, pt.lat), 4326)
            LIMIT 1
        ) AS n
        ORDER BY pt.idx
    """)
    with engine.connect() as connection:
        rows = connection.execute(query, params).mappings().all()
    return [
        {
            "index": int(row["idx"]),
            "from": {"lat": float(row["from_lat"]), "lon": float(row["from_lon"])},
            "osm_type": row["osm_type"],
            "osm_id": int(row["osm_id"]),
            "category": row["category"],
            "name": row["name"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
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
        SELECT DISTINCT ON (LEAST(e.u, e.v), GREATEST(e.u, e.v)) e.id, e.u, e.v,
               e.highway, e.attrs ->> 'name' AS name, e.length_m,
               ST_AsGeoJSON(e.geom) AS geometry_geojson
        FROM osm_edges AS e
        WHERE e.id <> :edge_id
          AND NOT (LEAST(e.u, e.v) = LEAST(:u, :v) AND GREATEST(e.u, e.v) = GREATEST(:u, :v))
          AND (e.u IN (:u, :v) OR e.v IN (:u, :v))
        ORDER BY LEAST(e.u, e.v), GREATEST(e.u, e.v), e.id
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
