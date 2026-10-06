import math

import pytest
import osmnx as ox

from route_optimizer.graph.spatial_store import (
    bbox_from_center,
    graph_from_rows,
    load_spatial_graph,
    nearest_spatial_node,
    persist_graph,
)
from route_optimizer.intelligence.graph_engine import GraphEngine


pytestmark = pytest.mark.unit


def test_spatial_graph_assembly_preserves_graphml_route_and_attributes(small_graph):
    node_rows = [
        {"id": node, "x": attrs["x"], "y": attrs["y"]}
        for node, attrs in small_graph.nodes(data=True)
    ]
    edge_rows = []
    for u, v, key, attrs in small_graph.edges(keys=True, data=True):
        edge_rows.append({
            "u": u,
            "v": v,
            "key": key,
            "length_m": attrs["length"],
            "highway": attrs["highway"],
            "attrs": dict(attrs),
            "geometry_geojson": None,
            "u_x": small_graph.nodes[u]["x"],
            "u_y": small_graph.nodes[u]["y"],
            "v_x": small_graph.nodes[v]["x"],
            "v_y": small_graph.nodes[v]["y"],
        })

    spatial_graph = graph_from_rows(node_rows, edge_rows)
    source_route = GraphEngine(small_graph).astar(1, 6)
    spatial_route = GraphEngine(spatial_graph).astar(1, 6)

    assert spatial_route["path"] == source_route["path"]
    assert spatial_route["distance"] == pytest.approx(source_route["distance"])
    assert spatial_graph[1][2][0]["maxspeed"] == "60"
    assert spatial_graph[2][3][0]["toll"] == "yes"


def test_spatial_graph_assembly_preserves_multivalue_highway_attribute():
    graph = graph_from_rows(
        [],
        [{
            "u": 1,
            "v": 2,
            "key": 0,
            "length_m": 100,
            "highway": "primary",
            "attrs": {"highway": ["primary", "secondary"]},
            "geometry_geojson": None,
            "u_x": 80.0,
            "u_y": 13.0,
            "v_x": 80.1,
            "v_y": 13.1,
        }],
    )

    assert graph[1][2][0]["highway"] == ["primary", "secondary"]


def test_bbox_uses_lon_lat_order_and_city_scale_meters():
    min_lon, min_lat, max_lon, max_lat = bbox_from_center((13.0, 80.0), 1000)

    assert min_lon < 80.0 < max_lon
    assert min_lat < 13.0 < max_lat
    assert max_lon - min_lon > max_lat - min_lat


def test_spatial_queries_use_indexable_bbox_and_metric_distance(small_graph):
    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows

    class Connection:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            self.statements.append((str(statement), params))
            if len(self.statements) == 1:
                return Result([
                    {"id": node, "x": attrs["x"], "y": attrs["y"]}
                    for node, attrs in small_graph.nodes(data=True)
                ])
            return Result([
                {"u": u, "v": v, "key": key, "length_m": data["length"],
                 "highway": data["highway"], "attrs": {}}
                for u, v, key, data in small_graph.edges(keys=True, data=True)
            ])

    class Engine:
        def __init__(self):
            self.connection = Connection()

        def connect(self):
            return self.connection

    engine = Engine()
    graph = load_spatial_graph(
        engine,
        bbox=(80.0, 13.0, 81.0, 14.0),
        center_point=(13.5, 80.5),
        radius_m=1000,
    )

    assert graph.number_of_edges() == small_graph.number_of_edges()
    # Two plain queries: nodes in the circle (indexable), then edges between them.
    assert len(engine.connection.statements) == 2
    node_sql, node_params = engine.connection.statements[0]
    edge_sql, edge_params = engine.connection.statements[1]
    assert "&& ST_MakeEnvelope" in node_sql
    assert "ST_DWithin" in node_sql
    assert node_params["lon"] == 80.5
    assert node_params["lat"] == 13.5
    assert "= ANY(" in edge_sql and "ST_DWithin" not in edge_sql
    assert sorted(edge_params["ids"]) == sorted(small_graph.nodes)


def test_postgis_nearest_node_matches_osmnx_for_twenty_points(small_graph):
    class Result:
        def __init__(self, node_id):
            self.node_id = node_id

        def scalar_one_or_none(self):
            return self.node_id

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            sql = str(statement)
            assert "ORDER BY geom::geography" in sql
            assert "<-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography" in sql
            assert "id = ANY(CAST(:node_ids AS BIGINT[]))" in sql
            assert params["node_ids"] == list(small_graph.nodes)
            assert -180 <= params["lon"] <= 180
            assert -90 <= params["lat"] <= 90

            def distance(node_id):
                node = small_graph.nodes[node_id]
                lat1, lat2 = math.radians(node["y"]), math.radians(params["lat"])
                delta_lat = lat2 - lat1
                delta_lon = math.radians(params["lon"] - node["x"])
                haversine = (
                    math.sin(delta_lat / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2)
                    * math.sin(delta_lon / 2) ** 2
                )
                return haversine

            return Result(min(
                small_graph.nodes,
                key=distance,
            ))

    class Engine:
        def connect(self):
            return Connection()

    points = [
        (
            13.080 + index * 0.0007,
            80.268 + index * 0.0011,
        )
        for index in range(20)
    ]
    for lat, lon in points:
        expected = ox.distance.nearest_nodes(small_graph, lon, lat)
        assert nearest_spatial_node(
            Engine(), small_graph.nodes, lon, lat
        ) == expected


def test_graph_ingestion_batches_and_ignores_conflicting_osm_ids(
    small_graph, monkeypatch
):
    from psycopg2 import extras

    statements = []

    def capture_values(_cursor, sql, rows, template=None):
        statements.append((sql, list(rows)))

    monkeypatch.setattr(extras, "execute_values", capture_values)

    class Connection:
        def cursor(self):
            class Cursor:
                def close(self):
                    pass

            return Cursor()

    persist_graph(Connection(), small_graph, batch_size=1)

    assert len(statements) == small_graph.number_of_nodes() + small_graph.number_of_edges()
    assert all("DO NOTHING" in sql for sql, _ in statements)
    assert all(len(rows) == 1 for _, rows in statements)


def test_graph_from_rows_keeps_only_routing_attributes():
    from route_optimizer.graph.spatial_store import graph_from_rows

    edge = {
        "u": 1, "v": 2, "key": 0, "length_m": 120.0, "highway": "primary",
        "u_x": 80.0, "u_y": 13.0, "v_x": 80.1, "v_y": 13.1,
        "attrs": {"maxspeed": "50", "lanes": "2", "osmid": 99, "ref": "NH48",
                  "bridge": "yes", "geometry": "ignored"},
    }

    graph = graph_from_rows([], [edge])

    data = graph.get_edge_data(1, 2)[0]
    assert data == {"maxspeed": "50", "lanes": "2", "length": 120.0, "highway": "primary"}


def test_persist_graph_commits_each_batch_and_stores_only_routing_attributes(
    small_graph, monkeypatch
):
    from psycopg2 import extras

    small_graph.edges[1, 2, 0]["osmid"] = 12345
    small_graph.edges[1, 2, 0]["bridge"] = "yes"
    edge_rows = []
    monkeypatch.setattr(
        extras, "execute_values",
        lambda _c, sql, rows, template=None: edge_rows.extend(
            rows if "osm_edges" in sql else []
        ),
    )

    class Connection:
        commits = 0

        def cursor(self):
            class Cursor:
                def close(self):
                    pass

            return Cursor()

        def commit(self):
            Connection.commits += 1

    connection = Connection()
    persist_graph(connection, small_graph, batch_size=5, commit_each_batch=True)

    # 6 nodes -> 2 commits, 14 edges -> 3 commits at batch_size=5
    assert connection.commits == 5
    stored = [row[-1].adapted for row in edge_rows]
    assert all(set(attrs) <= {"highway", "maxspeed", "lanes", "toll", "junction", "name", "oneway"} for attrs in stored)


def test_corridor_graph_selects_nodes_near_the_trip_line_then_their_edges(small_graph):
    from route_optimizer.graph.spatial_store import corridor_bbox, load_corridor_graph

    seen = []

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            seen.append((str(statement), params))
            if len(seen) == 1:
                return Result([
                    {"id": n, "x": a["x"], "y": a["y"]}
                    for n, a in small_graph.nodes(data=True)
                ])
            return Result([
                {"u": u, "v": v, "key": k, "length_m": d["length"],
                 "highway": d["highway"], "attrs": {}}
                for u, v, k, d in small_graph.edges(keys=True, data=True)
            ])

    class Engine:
        def connect(self):
            return Connection()

    points = [(13.08, 80.27), (13.04, 80.20)]
    graph = load_corridor_graph(Engine(), points, 2500.0)

    assert graph.number_of_edges() == small_graph.number_of_edges()
    assert all("x" in d and "y" in d for _, d in graph.nodes(data=True))
    node_sql, node_params = seen[0]
    edge_sql, edge_params = seen[1]
    assert node_params["path_wkt"] == "LINESTRING(80.27 13.08, 80.2 13.04)"
    assert node_params["buffer_m"] == 2500.0
    assert "&& ST_MakeEnvelope" in node_sql and "ST_DWithin" in node_sql
    assert "= ANY(" in edge_sql and "ST_DWithin" not in edge_sql
    assert "JOIN" not in edge_sql  # no planner-dependent join over the node set
    min_lon, min_lat, max_lon, max_lat = corridor_bbox(points, 2500.0)
    assert min_lon < 80.2 and max_lon > 80.27 and min_lat < 13.04 and max_lat > 13.08


def test_corridor_buffer_scales_with_trip_length_within_bounds():
    from route_optimizer.graph.manager import corridor_buffer_m

    assert corridor_buffer_m([(13.0, 80.0), (13.001, 80.0)]) == 2000.0       # tiny trip: floor
    assert 2500 < corridor_buffer_m([(13.0418, 80.2341), (13.0382, 80.1565)]) < 3500
    assert corridor_buffer_m([(13.0, 80.0), (11.0, 77.0)]) == 6000.0         # very long: cap


def test_places_along_route_filters_by_distance_to_the_route_line_in_travel_order():
    from route_optimizer.graph.spatial_queries import places_along_route

    seen = []

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{
                "osm_type": "node", "osm_id": 7, "category": "hospital", "name": "H",
                "attrs": {}, "lat": 13.04, "lon": 80.24,
                "distance_from_route_m": 41.26, "along_m": 1234.56,
            }]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            seen.append((str(statement), params))
            return Result()

    class Engine:
        def connect(self):
            return Connection()

    items = places_along_route(
        Engine(), [(80.23, 13.04), (80.28, 13.05)], 500.0, category="hospital", limit=10
    )

    sql, params = seen[0]
    assert params["wkt"] == "LINESTRING(80.23 13.04, 80.28 13.05)"
    assert params["distance_m"] == 500.0 and params["category"] == "hospital"
    assert "ST_Expand" in sql and "ST_DWithin" in sql   # indexed bbox, then metres
    assert "ST_LineLocatePoint" in sql and "ORDER BY along_m" in sql
    assert items == [{
        "osm_type": "node", "osm_id": 7, "category": "hospital", "name": "H",
        "attrs": {}, "lat": 13.04, "lon": 80.24,
        "distance_from_route_m": 41.3, "along_m": 1234.6,
    }]
