import pytest
from sqlalchemy import inspect, text

from app.models import db


pytestmark = pytest.mark.integration


def test_baseline_migration_recreates_current_sqlite_schema(flask_app):
    with flask_app.app_context():
        inspector = inspect(db.engine)
        assert set(inspector.get_table_names()) >= {
            "users",
            "search_history",
            "alembic_version",
        }
        assert {column["name"] for column in inspector.get_columns("users")} == {
            "id",
            "username",
            "password_hash",
            "role",
        }
        assert {column["name"] for column in inspector.get_columns("search_history")} == {
            "id",
            "user_id",
            "origin",
            "destination",
            "route_type",
            "vehicle_type",
            "distance_m",
            "estimated_time_min",
            "result_json",
            "created_at",
        }
        revision = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

        spatial_tables = {"osm_nodes", "osm_edges"} & set(inspector.get_table_names())

    assert revision == "20261005_0002"
    assert spatial_tables == set()
