import json
import logging
import math
from typing import Iterable, Mapping, Sequence, Tuple

import networkx as nx
from shapely.geometry import LineString
from shapely import wkt
from sqlalchemy import text

logger = logging.getLogger(__name__)


def bbox_from_center(
    center_point: Tuple[float, float], radius_m: float
) -> Tuple[float, float, float, float]:
    lat, lon = center_point
    lat_delta = radius_m / 111_320.0
    lon_delta = min(
        radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.01)),
        180.0,
    )
    return (
        max(-180.0, lon - lon_delta),
        max(-90.0, lat - lat_delta),
        min(180.0, lon + lon_delta),
        min(90.0, lat + lat_delta),
    )


# Edge attributes the router actually reads. Everything else OSM stores per
# edge (osmid, ref, bridge, shapely geometry...) is dropped: with ~150k edges
# the full attribute dicts cost several GB, far over a 512 MB instance.
_EDGE_ATTRS = ("highway", "maxspeed", "lanes", "toll", "junction", "name", "oneway")


def graph_from_rows(
    node_rows: Iterable[Mapping], edge_rows: Iterable[Mapping]
) -> nx.MultiDiGraph:
    """Build a request graph. Edge rows may carry endpoint coordinates
    (u_x/u_y/v_x/v_y) or rely on node_rows; only edge endpoints become nodes."""
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "epsg:4326"
    coords = {
        int(row["id"]): (float(row["x"]), float(row["y"])) for row in node_rows
    }

    def add_endpoint(node_id, x=None, y=None):
        if x is None:
            x, y = coords[node_id]
        graph.add_node(node_id, x=float(x), y=float(y))

    for row in edge_rows:
        u, v, key = int(row["u"]), int(row["v"]), int(row["key"])
        add_endpoint(u, row.get("u_x"), row.get("u_y"))
        add_endpoint(v, row.get("v_x"), row.get("v_y"))
        attrs = row["attrs"] or {}
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        if not isinstance(attrs, dict):
            raise ValueError(f"Edge {u}->{v} has non-object attrs")
        slim = {name: attrs[name] for name in _EDGE_ATTRS if name in attrs}
        slim["length"] = float(row["length_m"])
        slim.setdefault("highway", row["highway"])
        graph.add_edge(u, v, key=key, **slim)

    return graph


_EDGES_BETWEEN_NODES = text(
    """
    SELECT e.u, e.v, e.key, e.length_m, e.highway, e.attrs
    FROM osm_edges AS e
    WHERE e.u = ANY(CAST(:ids AS BIGINT[])) AND e.v = ANY(CAST(:ids AS BIGINT[]))
    """
)


def _load_graph_between_selected_nodes(engine, node_query, params) -> nx.MultiDiGraph:
    """Pick nodes with a spatial query, then fetch the edges joining two of them.

    Two plain queries instead of one CTE join: Postgres estimates the node set
    at a handful of rows and can choose a nested loop that rescans it for every
    edge, which ran for 10+ minutes once osm_edges passed ~450k rows.
    """
    with engine.connect() as connection:
        node_rows = connection.execute(node_query, params).mappings().all()
        node_ids = [int(row["id"]) for row in node_rows]
        if not node_ids:
            return graph_from_rows([], [])
        edge_rows = connection.execute(
            _EDGES_BETWEEN_NODES, {"ids": node_ids}
        ).mappings().all()
    return graph_from_rows(node_rows, edge_rows)


def load_spatial_graph(engine, bbox, center_point, radius_m) -> nx.MultiDiGraph:
    min_lon, min_lat, max_lon, max_lat = bbox
    lat, lon = center_point
    query_params = {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
        "lon": lon,
        "lat": lat,
        "radius_m": radius_m,
    }
    # Nodes inside the circle (a cheap indexed point test), then the edges
    # joining two of them -- the truncation osmnx.graph_from_point applies.
    # ST_DWithin on every edge's linestring as geography cannot use the index
    # and was ~10x slower.
    node_query = text(
        """
        SELECT id, ST_X(geom) AS x, ST_Y(geom) AS y
        FROM osm_nodes
        WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
          AND ST_DWithin(
              geom::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :radius_m
          )
        """
    )
    return _load_graph_between_selected_nodes(engine, node_query, query_params)


def corridor_bbox(
    points: Sequence[Tuple[float, float]], buffer_m: float
) -> Tuple[float, float, float, float]:
    """Bounding box of (lat, lon) points grown by buffer_m on every side."""
    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    min_lon, min_lat, _, _ = bbox_from_center((min(lats), min(lons)), buffer_m)
    _, _, max_lon, max_lat = bbox_from_center((max(lats), max(lons)), buffer_m)
    return min_lon, min_lat, max_lon, max_lat


def load_corridor_graph(
    engine, points: Sequence[Tuple[float, float]], buffer_m: float
) -> nx.MultiDiGraph:
    """Request graph for a trip: only roads within buffer_m of the straight
    path origin -> waypoints -> destination, not a circle around its midpoint.

    A circle of radius 1.5x the trip length covers ~7x the area a corridor does,
    which on a dense city meant >150k edges and an out-of-memory kill.
    """
    min_lon, min_lat, max_lon, max_lat = corridor_bbox(points, buffer_m)
    wkt_line = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in points) + ")"
    node_query = text(
        """
        SELECT id, ST_X(geom) AS x, ST_Y(geom) AS y
        FROM osm_nodes
        WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
          AND ST_DWithin(
              geom::geography, ST_GeogFromText(CAST(:path_wkt AS TEXT)), :buffer_m
          )
        """
    )
    params = {
        "path_wkt": wkt_line, "buffer_m": buffer_m,
        "min_lon": min_lon, "min_lat": min_lat,
        "max_lon": max_lon, "max_lat": max_lat,
    }
    return _load_graph_between_selected_nodes(engine, node_query, params)


def nearest_spatial_node(
    engine, candidate_node_ids: Iterable[int], lon: float, lat: float
) -> int | None:
    node_ids = [int(node_id) for node_id in candidate_node_ids]
    if not node_ids:
        return None

    query = text(
        """
        SELECT id
        FROM osm_nodes
        WHERE id = ANY(CAST(:node_ids AS BIGINT[]))
        ORDER BY geom::geography
                 <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        node_id = connection.execute(
            query,
            {"node_ids": node_ids, "lon": lon, "lat": lat},
        ).scalar_one_or_none()
    return int(node_id) if node_id is not None else None


def persist_graph(
    connection,
    graph: nx.MultiDiGraph,
    batch_size: int = 1000,
    commit_each_batch: bool = False,
) -> None:
    """Insert a graph's nodes and edges, skipping rows that already exist.

    commit_each_batch commits after every batch so a long bulk load shows real
    progress and keeps its work if the connection drops; leave it off when the
    caller wants the whole graph in one transaction.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    from psycopg2.extras import Json, execute_values

    def json_value(value):
        return Json(value, dumps=lambda obj: json.dumps(obj, default=str))

    cursor = connection.cursor()

    def flush(sql, rows, template, label, done):
        if not rows:
            return
        execute_values(cursor, sql, rows, template=template)
        if commit_each_batch:
            connection.commit()
            logger.info("Persisted %s %s", done, label)
        rows.clear()

    node_sql = """
        INSERT INTO osm_nodes (id, geom) VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    node_template = "(%s, ST_GeomFromText(%s, 4326))"
    node_batch, nodes_done = [], 0
    for node_id, attrs in graph.nodes(data=True):
        if "x" not in attrs or "y" not in attrs:
            raise ValueError(f"OSM node {node_id} is missing x/y coordinates")
        node_batch.append(
            (int(node_id), f"POINT({float(attrs['x'])} {float(attrs['y'])})")
        )
        nodes_done += 1
        if len(node_batch) >= batch_size:
            flush(node_sql, node_batch, node_template, "nodes", nodes_done)
    flush(node_sql, node_batch, node_template, "nodes", nodes_done)

    edge_sql = """
        INSERT INTO osm_edges (u, v, key, length_m, highway, geom, attrs)
        VALUES %s
        ON CONFLICT (u, v, key) DO NOTHING
    """
    edge_template = "(%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s)"
    edge_batch, edges_done = [], 0
    for u, v, key, data in graph.edges(keys=True, data=True):
        if "length" not in data:
            raise ValueError(f"OSM edge {u}->{v} is missing length")
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]

        # Only the attributes the router reads (see _EDGE_ATTRS); the rest of
        # OSM's per-edge tags bloat each row several-fold for no benefit.
        attrs = {name: data[name] for name in _EDGE_ATTRS if name in data}
        geometry = data.get("geometry")
        if isinstance(geometry, str):
            geometry = wkt.loads(geometry)
        if geometry is None:
            start, end = graph.nodes[u], graph.nodes[v]
            geometry = LineString(
                [(float(start["x"]), float(start["y"])),
                 (float(end["x"]), float(end["y"]))]
            )
        edge_batch.append((
            int(u),
            int(v),
            int(key),
            float(data["length"]),
            str(highway),
            geometry.wkt,
            json_value(attrs),
        ))
        edges_done += 1
        if len(edge_batch) >= batch_size:
            flush(edge_sql, edge_batch, edge_template, "edges", edges_done)
    flush(edge_sql, edge_batch, edge_template, "edges", edges_done)
    cursor.close()
