"""Create PostGIS road-network storage.

Revision ID: 20261005_0002
Revises: 20261005_0001
"""
from alembic import op


revision = "20261005_0002"
down_revision = "20261005_0001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE TABLE osm_nodes (
            id BIGINT PRIMARY KEY,
            geom geometry(Point, 4326) NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_osm_nodes_geom ON osm_nodes USING GIST (geom)"
    )
    op.execute(
        """
        CREATE TABLE osm_edges (
            id BIGSERIAL PRIMARY KEY,
            u BIGINT NOT NULL,
            v BIGINT NOT NULL,
            key INTEGER NOT NULL,
            length_m DOUBLE PRECISION NOT NULL,
            highway VARCHAR(80) NOT NULL,
            geom geometry(LineString, 4326) NOT NULL,
            attrs JSONB NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT uq_osm_edges_u_v_key UNIQUE (u, v, key)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_osm_edges_geom ON osm_edges USING GIST (geom)"
    )
    op.execute("CREATE INDEX idx_osm_edges_u ON osm_edges (u)")
    op.execute("CREATE INDEX idx_osm_edges_v ON osm_edges (v)")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP TABLE osm_edges")
    op.execute("DROP TABLE osm_nodes")
