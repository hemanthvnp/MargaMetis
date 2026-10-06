import pytest

from app.routes import spatial as spatial_routes


pytestmark = pytest.mark.integration


@pytest.fixture
def postgis_mode(monkeypatch):
    monkeypatch.setattr(spatial_routes, '_spatial_supported', lambda: True)


@pytest.mark.parametrize('path', [
    '/api/spatial/within-area?polygon=13,80;13,81;14,81',
    '/api/spatial/compare-areas?lat1=13&lon1=80&radius1_m=500&lat2=13&lon2=80.1&radius2_m=500',
    '/api/spatial/nearest-each?points=13,80',
])
def test_overlay_endpoints_report_postgis_requirement_on_sqlite(client, path):
    assert client.get(path).status_code == 503


@pytest.mark.parametrize('query', [
    'polygon=13,80;13,81',                        # fewer than 3 vertices
    'polygon=13,80;13,81;abc',                    # malformed
    'polygon=13,80;13,81;95,81',                  # latitude out of range
    'polygon=13,80;13,81;14,81&category=casino',
    '',                                           # missing
])
def test_within_area_rejects_bad_polygons(client, postgis_mode, query):
    assert client.get(f'/api/spatial/within-area?{query}').status_code == 400


def test_within_area_passes_lon_lat_ring_and_returns_summary(client, postgis_mode, monkeypatch):
    seen = {}

    def fake(engine, ring, category=None, limit=200):
        seen.update(ring=ring, category=category)
        return {'area_km2': 3.6, 'centroid': {'lat': 13.04, 'lon': 80.23},
                'counts': {'hospital': 1}, 'most_central': {'name': 'H'},
                'items': [{'name': 'H'}]}

    monkeypatch.setattr(spatial_routes.spatial_queries, 'places_in_area', fake)

    response = client.get(
        '/api/spatial/within-area?polygon=13.05,80.22;13.05,80.24;13.03,80.24&category=hospital'
    )

    body = response.get_json()
    assert response.status_code == 200
    assert seen['ring'] == [(80.22, 13.05), (80.24, 13.05), (80.24, 13.03)]  # (lon, lat) for PostGIS
    assert seen['category'] == 'hospital'
    assert body['count'] == 1 and body['area_km2'] == 3.6


def test_within_area_rejects_self_crossing_and_huge_polygons(client, postgis_mode, monkeypatch):
    monkeypatch.setattr(spatial_routes.spatial_queries, 'places_in_area', lambda *a, **k: None)
    assert client.get('/api/spatial/within-area?polygon=13,80;14,81;13,81;14,80').status_code == 400

    monkeypatch.setattr(
        spatial_routes.spatial_queries, 'places_in_area',
        lambda *a, **k: {'area_km2': 900.0, 'items': [], 'counts': {}, 'most_central': None,
                         'centroid': {'lat': 0, 'lon': 0}},
    )
    response = client.get('/api/spatial/within-area?polygon=13,80;13,82;15,82')
    assert response.status_code == 400
    assert 'too large' in response.get_json()['error']


def test_compare_areas_returns_overlay(client, postgis_mode, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        spatial_routes.spatial_queries, 'compare_areas',
        lambda engine, a, b: seen.update(a=a, b=b)
        or {'area_km2': {'union': 23.28}, 'overlap_pct_of_smaller': 13.7},
    )

    response = client.get(
        '/api/spatial/compare-areas?lat1=13.04&lon1=80.23&radius1_m=2000'
        '&lat2=13.04&lon2=80.26&radius2_m=1500'
    )

    assert response.status_code == 200
    assert seen == {'a': (13.04, 80.23, 2000.0), 'b': (13.04, 80.26, 1500.0)}
    assert response.get_json()['overlap_pct_of_smaller'] == 13.7


def test_compare_areas_validates_radius(client, postgis_mode):
    response = client.get(
        '/api/spatial/compare-areas?lat1=13&lon1=80&radius1_m=0&lat2=13&lon2=80.1&radius2_m=500'
    )

    assert response.status_code == 400


@pytest.mark.parametrize('query', [
    '',
    'points=',
    'points=' + ';'.join(['13,80'] * 11),        # more than 10 points
    'points=13,80&category=casino',
])
def test_nearest_each_validates_points(client, postgis_mode, query):
    assert client.get(f'/api/spatial/nearest-each?{query}').status_code == 400


def test_nearest_each_returns_one_place_per_point(client, postgis_mode, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        spatial_routes.spatial_queries, 'nearest_place_to_each',
        lambda engine, pts, category=None: seen.update(pts=pts, category=category)
        or [{'index': 0, 'name': 'A', 'distance_m': 12.0},
            {'index': 1, 'name': 'B', 'distance_m': 40.0}],
    )

    response = client.get('/api/spatial/nearest-each?points=13.04,80.23;13.08,80.27&category=hospital')

    assert response.status_code == 200
    assert seen == {'pts': [(13.04, 80.23), (13.08, 80.27)], 'category': 'hospital'}
    assert response.get_json()['count'] == 2
