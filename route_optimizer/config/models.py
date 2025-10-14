from dataclasses import dataclass

@dataclass(frozen=True)
class RouteConfig:
    """
    Immutable configuration class for routing settings.

    Attributes:
        graph_cache_dir (str): Directory path to store or read cached graph data.
    """
    graph_cache_dir: str = "./graph_cache"
