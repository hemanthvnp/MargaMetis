import pytest

from app.routes import spatial as spatial_routes


pytestmark = pytest.mark.integration


@pytest.fixture
def postgis_mode(monkeypatch):
    monkeypatch.setattr(spatial_routes, '_spatial_supported', lambda: True)


@pytest.mark.parametrize('path', [
    '/api/spatial/nearby?lat=13.08&lon=80.27',
    '/api/spatial/adjacent-roads?lat=13.08&lon=80.27',
    '/api/spatial/summary?lat=13.08&lon=80.27',
])
def test_postgis_endpoints_report_requirement_on_sqlite(client, path):
    response = client.get(path)

    assert response.status_code == 503
    assert 'PostgreSQL/PostGIS' in response.get_json()['error']


@pytest.mark.parametrize('query', [
    'lat=abc&lon=80.27',
    'lat=91&lon=80.27',
    'lat=13.08',
    'lat=13.08&lon=80.27&radius_m=0',
    'lat=13.08&lon=80.27&radius_m=999999',
    'lat=13.08&lon=80.27&category=casino',
    'lat=13.08&lon=80.27&limit=1000',
])
def test_nearby_rejects_invalid_params(client, postgis_mode, query):
    response = client.get(f'/api/spatial/nearby?{query}')

    assert response.status_code == 400


def test_nearby_passes_validated_args_to_query(client, postgis_mode, monkeypatch):
    calls = []

    def fake_nearby(engine, lat, lon, radius_m, category=None, limit=20):
        calls.append((lat, lon, radius_m, category, limit))
        return [{'name': 'PSG Hospital', 'distance_m': 812.5}]

    monkeypatch.setattr(spatial_routes.spatial_queries, 'nearby_pois', fake_nearby)

    response = client.get(
        '/api/spatial/nearby?lat=11.02&lon=77.00&radius_m=3000&category=hospital&limit=5'
    )

    body = response.get_json()
    assert response.status_code == 200
    assert calls == [(11.02, 77.0, 3000.0, 'hospital', 5)]
    assert body['count'] == 1
    assert body['items'][0]['distance_m'] == 812.5


def test_nearby_accepts_place_name(client, postgis_mode, monkeypatch):
    monkeypatch.setattr(spatial_routes, '_geocode', lambda place: (11.0247, 77.0028))
    seen = []
    monkeypatch.setattr(
        spatial_routes.spatial_queries, 'nearby_pois',
        lambda engine, lat, lon, radius_m, **kw: seen.append((lat, lon)) or [],
    )

    response = client.get('/api/spatial/nearby?place=PSG Tech')

    assert response.status_code == 200
    assert seen == [(11.0247, 77.0028)]


def test_unknown_place_is_a_400(client, postgis_mode, monkeypatch):
    def boom(place):
        raise RuntimeError('not found')

    monkeypatch.setattr(spatial_routes, '_geocode', boom)

    response = client.get('/api/spatial/nearby?place=Nowhereville')

    assert response.status_code == 400
    assert 'Nowhereville' in response.get_json()['error']


def test_adjacent_roads_404_when_no_road_nearby(client, postgis_mode, monkeypatch):
    monkeypatch.setattr(
        spatial_routes.spatial_queries, 'adjacent_roads', lambda *a, **k: None
    )

    response = client.get('/api/spatial/adjacent-roads?lat=0&lon=0')

    assert response.status_code == 404


def test_distance_between_named_places_works_without_postgis(client, monkeypatch):
    coords = {'Chennai': (13.0827, 80.2707), 'Coimbatore': (11.0168, 76.9558)}
    monkeypatch.setattr(spatial_routes, '_geocode', lambda place: coords[place])

    response = client.get('/api/spatial/distance?from=Chennai&to=Coimbatore')

    body = response.get_json()
    assert response.status_code == 200
    assert 420 < body['distance_km'] < 435
    assert body['line']['coordinates'][0] == [80.2707, 13.0827]


def test_distance_requires_both_places(client):
    response = client.get('/api/spatial/distance?from=Chennai')

    assert response.status_code == 400
