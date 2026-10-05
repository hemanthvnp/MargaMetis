import pytest

from route_optimizer.config.models import RouteConfig
from route_optimizer.graph import manager as graph_manager_module
from route_optimizer.graph.manager import GraphManager


pytestmark = pytest.mark.integration


def test_sqlite_keeps_graphml_cache_and_download_fallback(
    flask_app, small_graph, monkeypatch, tmp_path
):
    downloads = []
    monkeypatch.setattr(
        graph_manager_module.ox,
        "graph_from_point",
        lambda *args, **kwargs: downloads.append((args, kwargs)) or small_graph,
    )
    monkeypatch.setattr(
        graph_manager_module,
        "load_spatial_graph",
        lambda *args, **kwargs: pytest.fail("SQLite must not issue PostGIS queries"),
    )
    manager = GraphManager(RouteConfig(graph_cache_dir=str(tmp_path)))

    with flask_app.app_context():
        first_graph = manager.load_graph((28.61, 77.21), 1000)
        second_graph = manager.load_graph((28.61, 77.21), 1000)

    assert first_graph.number_of_edges() == small_graph.number_of_edges()
    assert second_graph.number_of_edges() == small_graph.number_of_edges()
    assert len(downloads) == 1
    assert len(list(tmp_path.glob("*.graphml"))) == 1


def test_postgres_never_loads_the_regional_seed_into_memory(monkeypatch, tmp_path):
    """The seed GraphML needs ~850 MB of RAM; on PostGIS it is served from the
    database, so an in-region query must not parse it (Render OOM)."""
    from types import SimpleNamespace

    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    monkeypatch.setattr(graph_manager_module, "has_app_context", lambda: True)
    monkeypatch.setattr(
        graph_manager_module, "current_app",
        SimpleNamespace(extensions={"sqlalchemy": SimpleNamespace(engine=engine)}),
    )
    monkeypatch.setattr(
        graph_manager_module.ox, "load_graphml",
        lambda *a, **k: pytest.fail("regional seed must not be parsed on PostGIS"),
    )
    sentinel = object()
    manager = GraphManager(RouteConfig(graph_cache_dir=str(tmp_path)))
    monkeypatch.setattr(manager, "_load_postgis_graph", lambda *a, **k: sentinel)

    assert manager.load_graph((13.0602, 80.2540), 3000) is sentinel
