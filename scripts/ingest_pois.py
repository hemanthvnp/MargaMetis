#!/usr/bin/env python3
"""Idempotently ingest OSM points of interest (hospitals, schools, ...) into PostGIS.

Example:
    python scripts/ingest_pois.py --database-url $DATABASE_URL \
        --lat 13.0827 --lon 80.2707 --radius-m 10000
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import osmnx as ox
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from route_optimizer.graph.spatial_queries import POI_CATEGORIES  # noqa: E402

logger = logging.getLogger("ingest_pois")

_INSERT = """
    INSERT INTO osm_pois (osm_type, osm_id, category, name, attrs, geom)
    VALUES %s
    ON CONFLICT (osm_type, osm_id) DO NOTHING
"""
_TEMPLATE = "(%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))"


def fetch_pois(lat: float, lon: float, radius_m: int):
    """Yield (osm_type, osm_id, category, name, attrs, point_wkt) rows."""
    features = ox.features_from_point(
        (lat, lon), tags={"amenity": list(POI_CATEGORIES)}, dist=radius_m
    )
    for (osm_type, osm_id), row in features.iterrows():
        category = row.get("amenity")
        if category not in POI_CATEGORIES or row.geometry is None:
            continue
        point = row.geometry.representative_point()
        name = row.get("name")
        attrs = {
            key: str(row[key])
            for key in ("operator", "addr:street", "emergency", "healthcare")
            if key in row and isinstance(row[key], str)
        }
        yield (
            str(osm_type), int(osm_id), category,
            name if isinstance(name, str) else None,
            attrs, point.wkt,
        )


def ingest_pois(database_url: str, lat: float, lon: float, radius_m: int,
                batch_size: int = 1000) -> int:
    for legacy in ("postgres://", "postgresql://"):
        if database_url.startswith(legacy):
            database_url = "postgresql+psycopg2://" + database_url[len(legacy):]
            break
    engine = create_engine(database_url)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("POI ingestion requires a PostgreSQL/PostGIS database")

    from psycopg2.extras import Json, execute_values

    rows = [(t, i, c, n, Json(a), w) for t, i, c, n, a, w in fetch_pois(lat, lon, radius_m)]
    logger.info("Fetched %s POIs", len(rows))

    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()
        for start in range(0, len(rows), batch_size):
            execute_values(
                cursor, _INSERT, rows[start:start + batch_size], template=_TEMPLATE
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        engine.dispose()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius-m", type=int, default=10000)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = ingest_pois(args.database_url, args.lat, args.lon, args.radius_m)
    logger.info("Ingested %s POIs", count)


if __name__ == "__main__":
    main()
