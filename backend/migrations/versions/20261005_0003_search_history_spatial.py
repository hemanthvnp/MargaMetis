"""Add spatial search-history points and backfill stored coordinates.

Revision ID: 20261005_0003
Revises: 20261005_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20261005_0003"
down_revision = "20261005_0002"
branch_labels = None
depends_on = None


_NUMERIC = r"^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$"


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE search_history "
            "ADD COLUMN origin_geom geometry(Point, 4326)"
        )
        op.execute(
            "ALTER TABLE search_history "
            "ADD COLUMN dest_geom geometry(Point, 4326)"
        )
        op.execute(
            "CREATE INDEX idx_search_history_origin_geom "
            "ON search_history USING GIST (origin_geom)"
        )
        op.execute(
            "CREATE INDEX idx_search_history_dest_geom "
            "ON search_history USING GIST (dest_geom)"
        )
        for column in ("origin", "destination"):
            geom_column = "origin_geom" if column == "origin" else "dest_geom"
            lon = f"result_json -> '{column}' ->> 'lon'"
            lat = f"result_json -> '{column}' ->> 'lat'"
            op.execute(
                f"""
                UPDATE search_history
                SET {geom_column} = ST_SetSRID(
                    ST_MakePoint(({lon})::double precision, ({lat})::double precision),
                    4326
                )
                WHERE ({lon}) ~ '{_NUMERIC}'
                  AND ({lat}) ~ '{_NUMERIC}'
                """
            )
        return

    op.add_column(
        "search_history",
        sa.Column("origin_geom", sa.Text(), nullable=True),
    )
    op.add_column(
        "search_history",
        sa.Column("dest_geom", sa.Text(), nullable=True),
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("idx_search_history_dest_geom", table_name="search_history")
        op.drop_index("idx_search_history_origin_geom", table_name="search_history")
    op.drop_column("search_history", "dest_geom")
    op.drop_column("search_history", "origin_geom")
