import pytest

from app.routes import admin as admin_routes


pytestmark = pytest.mark.integration


def _make_admin(client):
    with client.session_transaction() as session:
        session['role'] = 'admin'


def test_spatial_analytics_requires_server_side_admin_role(client):
    response = client.get('/api/admin/spatial-analytics')

    assert response.status_code == 403


@pytest.mark.parametrize('value', ['0', '21', 'not-an-integer'])
def test_spatial_analytics_rejects_out_of_range_cluster_count(client, value):
    _make_admin(client)

    response = client.get(f'/api/admin/spatial-analytics?k={value}')

    assert response.status_code == 400
    assert response.get_json()['error'] == 'k must be an integer from 1 to 20'


def test_spatial_analytics_reports_postgis_requirement_on_sqlite(client):
    _make_admin(client)

    response = client.get('/api/admin/spatial-analytics')

    assert response.status_code == 503
    assert 'PostgreSQL/PostGIS' in response.get_json()['error']


def test_spatial_analytics_returns_clusters_and_heatmap(client, monkeypatch):
    _make_admin(client)
    monkeypatch.setattr(
        admin_routes, '_spatial_analytics_supported', lambda: True
    )
    calls = []

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return self.rows

    def fake_execute(statement, params=None):
        sql = str(statement)
        calls.append((sql, params))
        if 'ST_ClusterKMeans' in sql:
            return Result([
                {
                    'point_type': 'origin',
                    'cluster_id': 0,
                    'lat': 13.08,
                    'lon': 80.27,
                    'weight': 3,
                },
                {
                    'point_type': 'destination',
                    'cluster_id': 1,
                    'lat': 13.09,
                    'lon': 80.29,
                    'weight': 2,
                },
            ])
        return Result([{'lat': 13.08, 'lon': 80.27, 'weight': 3}])

    monkeypatch.setattr(admin_routes.db.session, 'execute', fake_execute)

    response = client.get('/api/admin/spatial-analytics?k=2')

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'k': 2,
        'clusters': {
            'origins': [{
                'cluster_id': 0,
                'lat': 13.08,
                'lon': 80.27,
                'weight': 3,
            }],
            'destinations': [{
                'cluster_id': 1,
                'lat': 13.09,
                'lon': 80.29,
                'weight': 2,
            }],
        },
        'heatmap': [[13.08, 80.27, 3]],
    }
    assert len(calls) == 2
    assert calls[0][1] == {'k': 2}
    assert all('search_history' in sql for sql, _ in calls)
