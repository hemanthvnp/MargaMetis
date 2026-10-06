from route_optimizer.graph.spatial_queries import (
    compare_areas, nearest_place_to_each, places_in_area,
)


def _recording_engine(rows_by_call):
    seen = []

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows

        def one(self):
            return self.rows[0]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            seen.append((str(statement), params))
            return Result(rows_by_call[len(seen) - 1])

    class Engine:
        def connect(self):
            return Connection()

    return Engine(), seen


def test_places_in_area_uses_containment_and_reports_most_central():
    place = {"osm_type": "node", "osm_id": 1, "category": "hospital", "name": "H", "attrs": {},
             "lat": 13.04, "lon": 80.23, "distance_to_centroid_m": 12.34}
    engine, seen = _recording_engine([
        [{"valid": True, "area_m2": 3_600_000.0, "lat": 13.0425, "lon": 80.235}],
        [place],
        [{"category": "hospital", "count": 1}],
    ])

    result = places_in_area(engine, [(80.22, 13.05), (80.24, 13.05), (80.24, 13.03)], "hospital")

    assert seen[0][1]["wkt"] == "POLYGON((80.22 13.05, 80.24 13.05, 80.24 13.03, 80.22 13.05))"  # closed
    sql = seen[1][0]
    assert "ST_Within" in sql and "p.geom && poly.geom" in sql
    assert result["area_km2"] == 3.6
    assert result["most_central"]["name"] == "H"
    assert result["counts"] == {"hospital": 1}


def test_places_in_area_returns_none_for_an_invalid_polygon():
    engine, _ = _recording_engine([[{"valid": False, "area_m2": 0.0, "lat": 0.0, "lon": 0.0}]])

    assert places_in_area(engine, [(0, 0), (1, 1), (1, 0), (0, 1)]) is None


def test_compare_areas_uses_postgis_set_operations():
    geo = '{"type":"Polygon","coordinates":[]}'
    engine, seen = _recording_engine([[{
        "area_a": 12_490_000.0, "area_b": 12_490_000.0, "area_union": 23_280_000.0,
        "area_intersection": 1_710_000.0, "area_sym_difference": 21_570_000.0,
        "a_geojson": geo, "b_geojson": geo, "union_geojson": geo, "intersection_geojson": geo,
    }]])

    result = compare_areas(engine, (13.04, 80.23, 2000.0), (13.04, 80.26, 2000.0))

    sql = seen[0][0]
    assert "ST_Union" in sql and "ST_Intersection" in sql and "ST_SymDifference" in sql
    assert result["area_km2"]["union"] == 23.28
    assert result["overlap_pct_of_smaller"] == 13.7


def test_nearest_place_to_each_is_a_lateral_knn_join():
    engine, seen = _recording_engine([[{
        "idx": 0, "from_lat": 13.04, "from_lon": 80.23, "osm_type": "node", "osm_id": 5,
        "category": "hospital", "name": "H", "lat": 13.041, "lon": 80.231, "distance_m": 150.66,
    }]])

    items = nearest_place_to_each(engine, [(13.04, 80.23)], "hospital")

    sql, params = seen[0]
    assert "CROSS JOIN LATERAL" in sql and "ORDER BY p.geom <->" in sql and "LIMIT 1" in sql
    assert params["lats"] == [13.04] and params["lons"] == [80.23]
    assert params["category"] == "hospital"
    assert items[0]["distance_m"] == 150.7
