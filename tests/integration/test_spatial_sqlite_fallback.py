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
