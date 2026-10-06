#!/usr/bin/env python3
"""Load the road network and places into an empty database; skip what exists.

Run by the `seed` service in docker-compose.yml, so `docker compose up` ends
with a database the app can use. Safe to run repeatedly: a table that already
has rows is left alone. Re-run it by hand with:

    docker compose run --rm seed
"""

import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ingest_graphs import ingest_graphs  # noqa: E402
from ingest_pois import ingest_pois  # noqa: E402

logger = logging.getLogger("seed")

SEED_GRAPH = ROOT / "route_optimizer" / "regional_seed" / "chennai_central.graphml"
# (name, lat, lon, radius_m): Chennai, plus PSG Tech in Coimbatore for demos.
POI_AREAS = [
    ("Chennai", 13.0602, 80.2540, 9000),
    ("Coimbatore", 11.0247, 77.0028, 7000),
]


def _driver_url(url: str) -> str:
    for legacy in ("postgres://", "postgresql://"):
        if url.startswith(legacy):
            return "postgresql+psycopg2://" + url[len(legacy):]
    return url


def _row_count(engine, table: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar())


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL is not set")
        return 1
    engine = create_engine(_driver_url(database_url))

    if _row_count(engine, "osm_edges") > 0:
        logger.info("Road network already loaded; skipping")
    elif not SEED_GRAPH.is_file():
        logger.warning("Seed graph %s is missing; routes outside cached areas will download", SEED_GRAPH)
    else:
        logger.info("Loading the Chennai road network (a few minutes)")
        ingest_graphs(database_url, [SEED_GRAPH], batch_size=5000)

    if _row_count(engine, "osm_pois") > 0:
        logger.info("Places already loaded; skipping")
    else:
        for name, lat, lon, radius_m in POI_AREAS:
            try:
                logger.info("Loading places around %s", name)
                ingest_pois(database_url, lat, lon, radius_m)
            except Exception as exc:  # Overpass can be slow or blocked; not fatal
                logger.warning("Could not load places for %s: %s", name, exc)
                logger.warning("Retry later with: docker compose run --rm seed")

    logger.info(
        "Seed complete: %s edges, %s places",
        _row_count(engine, "osm_edges"), _row_count(engine, "osm_pois"),
    )
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
