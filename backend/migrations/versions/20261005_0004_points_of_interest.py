"""Create PostGIS points-of-interest storage.

Revision ID: 20261005_0004
Revises: 20261005_0003
"""
from alembic import op


revision = "20261005_0004"
down_revision = "20261005_0003"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE TABLE osm_pois (
            id BIGSERIAL PRIMARY KEY,
            osm_type VARCHAR(16) NOT NULL,
            osm_id BIGINT NOT NULL,
            category VARCHAR(40) NOT NULL,
            name TEXT,
            attrs JSONB NOT NULL DEFAULT '{}'::jsonb,
            geom geometry(Point, 4326) NOT NULL,
            CONSTRAINT uq_osm_pois_type_id UNIQUE (osm_type, osm_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_osm_pois_geom ON osm_pois USING GIST (geom)")
    op.execute("CREATE INDEX idx_osm_pois_category ON osm_pois (category)")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP TABLE osm_pois")
