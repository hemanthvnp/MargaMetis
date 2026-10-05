#!/usr/bin/env python3
"""Idempotently ingest the baked and cached OSM GraphML graphs into PostGIS."""

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

from route_optimizer.graph.spatial_store import persist_graph  # noqa: E402

logger = logging.getLogger("ingest_graphs")


def _graph_files(root: Path, requested: list[Path] | None) -> list[Path]:
    if requested:
        paths = [path.resolve() for path in requested]
    else:
        primary = root / "chennai_central.graphml"
        if not primary.exists():
            logger.warning("Primary graph %s is absent", primary)
        paths = ([primary] if primary.exists() else []) + sorted(
            (root / "graph_cache").glob("*.graphml")
        )
    if not paths:
        raise FileNotFoundError(
            "No GraphML inputs found (expected chennai_central.graphml "
            "or graph_cache/*.graphml)"
        )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"GraphML input does not exist: {missing[0]}")
    return paths


def ingest_graphs(
    database_url: str,
    graph_files: list[Path],
    batch_size: int = 1000,
) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(database_url)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("Graph ingestion requires a PostgreSQL/PostGIS database")

    connection = engine.raw_connection()
    try:
        for path in graph_files:
            logger.info("Loading GraphML %s", path)
            graph = ox.load_graphml(path)
            logger.info(
                "Ingesting %s nodes and %s edges from %s",
                graph.number_of_nodes(),
                graph.number_of_edges(),
                path.name,
            )
            persist_graph(connection, graph, batch_size=batch_size)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URI (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--graph",
        dest="graphs",
        action="append",
        type=Path,
        help="GraphML input; repeat to ingest multiple files",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.database_url:
        parser.error("set DATABASE_URL or pass --database-url")
    graph_files = _graph_files(ROOT, args.graphs)
    ingest_graphs(args.database_url, graph_files, args.batch_size)
    logger.info("Graph ingestion complete")


if __name__ == "__main__":
    main()
