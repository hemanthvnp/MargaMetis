import pytest

from app.models import db
from app.routes.route_api import _history_geometry


pytestmark = pytest.mark.unit


def test_history_geometry_is_disabled_for_sqlite(flask_app):
    with flask_app.app_context():
        assert _history_geometry(
            {'origin': {'lat': 13.08, 'lon': 80.27}}, 'origin'
        ) is None


def test_history_geometry_builds_lon_lat_postgis_point(flask_app, monkeypatch):
    payload = {'origin': {'lat': 13.08, 'lon': 80.27}}
    with flask_app.app_context():
        monkeypatch.setattr(db.engine.dialect, 'name', 'postgresql')

        point = _history_geometry(payload, 'origin')

    assert str(point) == 'POINT(80.27 13.08)'
    assert point.srid == 4326


def test_history_geometry_ignores_missing_or_invalid_coordinates(flask_app):
    with flask_app.app_context():
        assert _history_geometry({}, 'origin') is None
        assert _history_geometry(
            {'origin': {'lat': 91, 'lon': 80}}, 'origin'
        ) is None
