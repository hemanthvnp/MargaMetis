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
            "origin_geom",
            "dest_geom",
            "created_at",
        }
        revision = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

        spatial_tables = {"osm_nodes", "osm_edges"} & set(inspector.get_table_names())

    assert revision == "20261005_0004"
    assert spatial_tables == set()


def test_upgrade_adopts_database_that_predates_alembic(monkeypatch, tmp_path):
    """Production DBs were built with create_all(); the first deploy's
    `flask db upgrade` must adopt those tables, not fail on CREATE TABLE."""
    import sqlite3

    from flask_migrate import upgrade

    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL);
        CREATE TABLE search_history (
            id INTEGER PRIMARY KEY, user_id INTEGER, origin VARCHAR(255) NOT NULL,
            destination VARCHAR(255) NOT NULL, route_type VARCHAR(50) NOT NULL,
            vehicle_type VARCHAR(50) NOT NULL, distance_m FLOAT NOT NULL,
            estimated_time_min FLOAT, result_json JSON,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO users (username, password_hash, role) VALUES ('keep', 'x', 'user');
        """
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    from app import create_app

    app = create_app("testing")
    with app.app_context():
        upgrade(directory=app.config["MIGRATIONS_DIR"])
        revision = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        users = db.session.execute(text("SELECT username FROM users")).scalars().all()
        columns = {c["name"] for c in inspect(db.engine).get_columns("search_history")}
        db.session.remove()
        db.engine.dispose()

    assert revision == "20261005_0004"
    assert users == ["keep"]
    assert {"origin_geom", "dest_geom"} <= columns


@pytest.mark.parametrize("url", [
    "postgres://u:p@host:5432/db",
    "postgresql://u:p@host:5432/db",
])
def test_postgres_urls_pin_the_psycopg2_driver(monkeypatch, url):
    """SQLAlchemy 2.1 defaults bare postgresql:// to psycopg3, which the image
    does not install -- the app must name psycopg2 explicitly."""
    monkeypatch.setenv("DATABASE_URL", url)
    from app import create_app

    app = create_app("testing")

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "postgresql+psycopg2://u:p@host:5432/db"


def test_postgres_engine_gets_a_statement_timeout(monkeypatch):
    """A runaway query must fail fast: one sync worker serves all requests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    from app import create_app

    options = create_app("testing").config["SQLALCHEMY_ENGINE_OPTIONS"]

    assert "statement_timeout=60000" in options["connect_args"]["options"]
