class RouteConfig(object):
    def __init__(self, graph_cache_dir="./graph_cache"):
        self.graph_cache_dir = graph_cache_dir

    def __repr__(self):
        return "RouteConfig(graph_cache_dir='{}')".format(self.graph_cache_dir)
