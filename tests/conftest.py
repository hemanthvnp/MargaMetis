import os
import socket
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import networkx as nx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
for _p in (str(_BACKEND_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ----------------------------------------------------------------------
# small_graph — deterministic, hand-built, OSMnx-shaped MultiDiGraph
# ----------------------------------------------------------------------
#
#      1 --- 2 --- 3
#      |     |     |
#      4 --- 5 --- 6
#
# 1: origin corner, 6: opposite corner. Mixed highway types/speeds/tolls
# so cost-function and ranking behaviour has something to differentiate.

def _build_small_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.graph["crs"] = "epsg:4326"
    coords = {
        1: (13.0827, 80.2707),
        2: (13.0827, 80.2807),
        3: (13.0827, 80.2907),
        4: (13.0927, 80.2707),
        5: (13.0927, 80.2807),
        6: (13.0927, 80.2907),
    }
    for node_id, (lat, lon) in coords.items():
        g.add_node(node_id, y=lat, x=lon)

    edges = [
        (1, 2, {"length": 1000.0, "highway": "primary", "maxspeed": "60"}),
        (2, 3, {"length": 1000.0, "highway": "motorway", "maxspeed": "100", "toll": "yes"}),
        (4, 5, {"length": 1000.0, "highway": "residential", "maxspeed": "30"}),
        (5, 6, {"length": 1000.0, "highway": "secondary", "maxspeed": "50"}),
        (1, 4, {"length": 1100.0, "highway": "tertiary", "maxspeed": "40"}),
        (2, 5, {"length": 1100.0, "highway": "unclassified", "maxspeed": "40"}),
        (3, 6, {"length": 1100.0, "highway": "residential", "maxspeed": "30"}),
    ]
    for u, v, data in edges:
        g.add_edge(u, v, **data)
        g.add_edge(v, u, **data)

    return g


@pytest.fixture(autouse=True)
def _no_groq_key(monkeypatch):
    """Force ConstraintEngine's deterministic rule-based fallback in every test.

    Keeps the suite free/offline/deterministic. The repo's .env has a live
    Groq key on disk but nothing auto-loads it via python-dotenv, so this is
    a belt-and-braces guard against it leaking in from the shell environment.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


@pytest.fixture
def small_graph() -> nx.MultiDiGraph:
    return _build_small_graph()


@pytest.fixture
def tiny_graph() -> nx.MultiDiGraph:
    """A trivial 3-node line graph for smoke tests."""
    g = nx.MultiDiGraph()
    g.graph["crs"] = "epsg:4326"
    g.add_node(1, y=13.08, x=80.27)
    g.add_node(2, y=13.09, x=80.28)
    g.add_node(3, y=13.10, x=80.29)
    g.add_edge(1, 2, length=500.0, highway="residential", maxspeed="30")
    g.add_edge(2, 3, length=500.0, highway="residential", maxspeed="30")
    return g


# ----------------------------------------------------------------------
# redis_up — pings REDIS_URL, used to skip Redis-dependent tests cleanly
# ----------------------------------------------------------------------

@pytest.fixture(scope="session")
def redis_up() -> bool:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(url)
    host, port = parsed.hostname or "localhost", parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def skip_if_no_redis(redis_up: bool) -> None:
    if not redis_up:
        pytest.skip(f"Redis not reachable at {os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}")


# ----------------------------------------------------------------------
# Flask app / client — sqlite-backed, no MySQL/Docker required
# ----------------------------------------------------------------------

@pytest.fixture
def flask_app(monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.pop("GROQ_API_KEY", None)
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

    from app import create_app
    from flask_migrate import upgrade

    app = create_app("testing")
    app.config["TESTING"] = True
    with app.app_context():
        upgrade(directory=app.config["MIGRATIONS_DIR"])
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(flask_app):
    client = flask_app.test_client()
    response = client.get("/api/auth/me")
    client.environ_base["HTTP_X_CSRFTOKEN"] = response.get_json()["csrf_token"]
    return client
