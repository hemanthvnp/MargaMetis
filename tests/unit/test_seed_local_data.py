import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_local_data.py"


@pytest.fixture
def seed(monkeypatch):
    spec = importlib.util.spec_from_file_location("seed_local_data", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/margametis")
    monkeypatch.setattr(module, "create_engine", lambda url: type("E", (), {"dispose": lambda s: None})())
    return module


def _run(seed, monkeypatch, edges, pois, poi_error=None):
    calls = {"graph": 0, "pois": []}
    monkeypatch.setattr(seed, "_row_count", lambda engine, table: edges if table == "osm_edges" else pois)
    monkeypatch.setattr(seed, "ingest_graphs", lambda *a, **k: calls.__setitem__("graph", calls["graph"] + 1))

    def fake_pois(url, lat, lon, radius):
        if poi_error:
            raise poi_error
        calls["pois"].append((lat, lon, radius))

    monkeypatch.setattr(seed, "ingest_pois", fake_pois)
    return seed.main(), calls


def test_seed_loads_everything_into_an_empty_database(seed, monkeypatch):
    status, calls = _run(seed, monkeypatch, edges=0, pois=0)

    assert status == 0
    assert calls["graph"] == 1
    assert len(calls["pois"]) == 2          # Chennai and Coimbatore


def test_seed_is_idempotent_when_data_is_already_loaded(seed, monkeypatch):
    status, calls = _run(seed, monkeypatch, edges=158659, pois=2490)

    assert status == 0
    assert calls == {"graph": 0, "pois": []}


def test_seed_does_not_fail_when_the_places_download_fails(seed, monkeypatch):
    status, calls = _run(seed, monkeypatch, edges=158659, pois=0, poi_error=RuntimeError("overpass down"))

    assert status == 0                       # the app still works without places


def test_seed_requires_a_database_url(seed, monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    assert seed.main() == 1
