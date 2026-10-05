import heapq
import math
import time
from typing import Callable, Dict, List, Optional, Tuple

import networkx as nx


class GraphEngine:

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self._coord_cache: Dict[int, Tuple[float, float]] = {}

    def _coords(self, node: int) -> Tuple[float, float]:
        if node not in self._coord_cache:
            d = self.graph.nodes[node]
            self._coord_cache[node] = (float(d["y"]), float(d["x"]))
        return self._coord_cache[node]

    def _haversine(self, a: int, b: int) -> float:
        lat1, lon1 = self._coords(a)
        lat2, lon2 = self._coords(b)
        R = 6_371_000.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        h = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1))
             * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2.0 * math.asin(math.sqrt(max(0.0, h)))

    def _edge_weight(
        self,
        u: int,
        v: int,
        weight_fn: Optional[Callable] = None,
        prev_node: Optional[int] = None,
    ) -> float:
        # OSMnx uses MultiDiGraph so there can be parallel edges — take the cheapest
        edge_dict = self.graph.get_edge_data(u, v)
        if not edge_dict:
            return float("inf")
        if weight_fn is not None:
            if getattr(weight_fn, "requires_prev_node", False):
                return min(
                    weight_fn(u, v, data, prev_node) for data in edge_dict.values()
                )
            return min(weight_fn(u, v, data) for data in edge_dict.values())
        return min(data.get("length", float("inf")) for data in edge_dict.values())

    def _path_cost(self, path: List[int], weight_fn: Optional[Callable] = None) -> float:
        return sum(
            self._edge_weight(
                path[i],
                path[i + 1],
                weight_fn,
                path[i - 1] if i > 0 else None,
            )
            for i in range(len(path) - 1)
        )

    def _predecessor_search(
        self,
        origin: int,
        destination: int,
        weight_fn: Callable,
        blocked_edges: Optional[set] = None,
        blocked_nodes: Optional[set] = None,
        use_heuristic: bool = True,
    ) -> Dict:
        # Turn costs depend on the incoming edge, so each search state must
        # include both the previous and current node.
        t0 = time.perf_counter()
        start = (None, origin)
        g: Dict[Tuple[Optional[int], int], float] = {start: 0.0}
        came_from: Dict[
            Tuple[Optional[int], int], Tuple[Optional[int], int]
        ] = {}
        initial_h = self._haversine(origin, destination) if use_heuristic else 0.0
        heap = [(initial_h, 0.0, start)]
        closed: set = set()
        nodes_explored = 0
        blocked_edges = blocked_edges or set()
        blocked_nodes = blocked_nodes or set()
        end_state = None

        while heap:
            _, _, state = heapq.heappop(heap)
            if state in closed:
                continue
            closed.add(state)
            nodes_explored += 1
            prev_node, u = state
            if u == destination:
                end_state = state
                break
            for v in self.graph.successors(u):
                if v in blocked_nodes or (u, v) in blocked_edges:
                    continue
                next_state = (u, v)
                ng = g[state] + self._edge_weight(
                    u, v, weight_fn, prev_node=prev_node
                )
                if ng < g.get(next_state, float("inf")):
                    g[next_state] = ng
                    came_from[next_state] = state
                    heuristic = self._haversine(v, destination) if use_heuristic else 0.0
                    heapq.heappush(heap, (ng + heuristic, ng, next_state))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if end_state is None:
            return {
                "path": None,
                "distance": float("inf"),
                "time_ms": elapsed_ms,
                "nodes_explored": nodes_explored,
            }

        states = [end_state]
        while states[-1] != start:
            states.append(came_from[states[-1]])
        states.reverse()
        return {
            "path": [node for _, node in states],
            "distance": g[end_state],
            "time_ms": elapsed_ms,
            "nodes_explored": nodes_explored,
        }

    @staticmethod
    def _reconstruct(came_from: Dict, start: int, end: int) -> List[int]:
        path: List[int] = []
        cur = end
        while cur != start:
            path.append(cur)
            cur = came_from[cur]
        path.append(start)
        path.reverse()
        return path

    def dijkstra(self, origin: int, destination: int,
                 weight_fn: Optional[Callable] = None) -> Dict:
        if weight_fn is not None and getattr(weight_fn, "requires_prev_node", False):
            return self._predecessor_search(
                origin, destination, weight_fn, use_heuristic=False
            )
        t0 = time.perf_counter()
        dist: Dict[int, float] = {origin: 0.0}
        came_from: Dict[int, int] = {}
        heap = [(0.0, origin)]
        closed: set = set()
        nodes_explored = 0

        while heap:
            d, u = heapq.heappop(heap)
            if u in closed:
                continue
            closed.add(u)
            nodes_explored += 1
            if u == destination:
                break
            for v in self.graph.successors(u):
                nd = d + self._edge_weight(u, v, weight_fn)
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    came_from[v] = u
                    heapq.heappush(heap, (nd, v))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if destination not in dist:
            return {"path": None, "distance": float("inf"),
                    "time_ms": elapsed_ms, "nodes_explored": nodes_explored}
        return {"path": self._reconstruct(came_from, origin, destination),
                "distance": dist[destination],
                "time_ms": elapsed_ms, "nodes_explored": nodes_explored}

    def astar(self, origin: int, destination: int,
              weight_fn: Optional[Callable] = None) -> Dict:
        if weight_fn is not None and getattr(weight_fn, "requires_prev_node", False):
            return self._predecessor_search(origin, destination, weight_fn)
        t0 = time.perf_counter()
        g: Dict[int, float] = {origin: 0.0}
        came_from: Dict[int, int] = {}
        # (f_score, g_score, node) — storing g separately avoids a dict lookup at pop
        heap = [(self._haversine(origin, destination), 0.0, origin)]
        closed: set = set()
        nodes_explored = 0

        while heap:
            _, g_val, u = heapq.heappop(heap)
            if u in closed:
                continue
            closed.add(u)
            nodes_explored += 1
            if u == destination:
                break
            for v in self.graph.successors(u):
                ng = g[u] + self._edge_weight(u, v, weight_fn)
                if ng < g.get(v, float("inf")):
                    g[v] = ng
                    came_from[v] = u
                    heapq.heappush(heap, (ng + self._haversine(v, destination), ng, v))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if destination not in g:
            return {"path": None, "distance": float("inf"),
                    "time_ms": elapsed_ms, "nodes_explored": nodes_explored}
        return {"path": self._reconstruct(came_from, origin, destination),
                "distance": g[destination],
                "time_ms": elapsed_ms, "nodes_explored": nodes_explored}

    def bidirectional_astar(self, origin: int, destination: int,
                            weight_fn: Optional[Callable] = None) -> Dict:
        if weight_fn is not None and getattr(weight_fn, "requires_prev_node", False):
            raise ValueError(
                "Bidirectional A* cannot use predecessor-aware edge costs; use A*."
            )
        if origin == destination:
            return {"path": [origin], "distance": 0.0, "time_ms": 0.0, "nodes_explored": 0}

        t0 = time.perf_counter()

        g_fwd: Dict[int, float] = {origin: 0.0}
        prev_fwd: Dict[int, Optional[int]] = {origin: None}
        heap_fwd = [(self._haversine(origin, destination), 0.0, origin)]
        closed_fwd: Dict[int, float] = {}

        g_bwd: Dict[int, float] = {destination: 0.0}
        prev_bwd: Dict[int, Optional[int]] = {destination: None}
        heap_bwd = [(self._haversine(destination, origin), 0.0, destination)]
        closed_bwd: Dict[int, float] = {}

        best = float("inf")
        meeting: Optional[int] = None
        nodes_explored = 0

        while heap_fwd or heap_bwd:
            if heap_fwd:
                _, _, u = heapq.heappop(heap_fwd)
                if u not in closed_fwd:
                    closed_fwd[u] = g_fwd[u]
                    nodes_explored += 1
                    if u in closed_bwd:
                        c = g_fwd[u] + g_bwd[u]
                        if c < best:
                            best, meeting = c, u
                    for v in self.graph.successors(u):
                        ng = g_fwd[u] + self._edge_weight(u, v, weight_fn)
                        if ng < g_fwd.get(v, float("inf")):
                            g_fwd[v] = ng
                            prev_fwd[v] = u
                            heapq.heappush(heap_fwd,
                                           (ng + self._haversine(v, destination), ng, v))
                        if v in closed_bwd and ng + g_bwd[v] < best:
                            best, meeting = ng + g_bwd[v], v

            if heap_bwd:
                _, _, u = heapq.heappop(heap_bwd)
                if u not in closed_bwd:
                    closed_bwd[u] = g_bwd[u]
                    nodes_explored += 1
                    if u in closed_fwd:
                        c = g_fwd[u] + g_bwd[u]
                        if c < best:
                            best, meeting = c, u
                    for v in self.graph.predecessors(u):
                        ng = g_bwd[u] + self._edge_weight(v, u, weight_fn)
                        if ng < g_bwd.get(v, float("inf")):
                            g_bwd[v] = ng
                            prev_bwd[v] = u
                            heapq.heappush(heap_bwd,
                                           (ng + self._haversine(v, origin), ng, v))
                        if v in closed_fwd and g_fwd[v] + ng < best:
                            best, meeting = g_fwd[v] + ng, v

            # Stop when the minimum possible improvement from either frontier
            # can't beat the best path found so far
            g_top_fwd = heap_fwd[0][1] if heap_fwd else float("inf")
            g_top_bwd = heap_bwd[0][1] if heap_bwd else float("inf")
            if g_top_fwd + g_top_bwd >= best:
                break

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if meeting is None:
            return {"path": None, "distance": float("inf"),
                    "time_ms": elapsed_ms, "nodes_explored": nodes_explored}

        fwd_path: List[int] = []
        cur: Optional[int] = meeting
        while cur is not None:
            fwd_path.append(cur)
            cur = prev_fwd.get(cur)
        fwd_path.reverse()

        bwd_path: List[int] = []
        cur = prev_bwd.get(meeting)
        while cur is not None:
            bwd_path.append(cur)
            cur = prev_bwd.get(cur)

        return {"path": fwd_path + bwd_path, "distance": best,
                "time_ms": elapsed_ms, "nodes_explored": nodes_explored}

    def yen_k_shortest(self, origin: int, destination: int,
                       k: int = 3, weight_fn: Optional[Callable] = None) -> List[Dict]:
        # Uses edge/node blocking instead of graph.copy() on every spur.
        # Copying a 50K-node graph per iteration brought total time to ~169s;
        # this version runs in ~800ms for k=3.
        t0 = time.perf_counter()

        first = self.astar(origin, destination, weight_fn)
        if first["path"] is None:
            return []

        A = [{"path": first["path"], "distance": first["distance"]}]
        B: List[Dict] = []

        for ki in range(1, k):
            prev_path = A[ki - 1]["path"]

            for i in range(len(prev_path) - 1):
                spur_node = prev_path[i]
                root_path = prev_path[:i + 1]
                root_cost = self._path_cost(root_path, weight_fn)

                blocked_edges: set = set()
                blocked_nodes: set = set(root_path[:-1])

                for path_info in A:
                    p = path_info["path"]
                    if len(p) > i and p[:i + 1] == root_path:
                        blocked_edges.add((p[i], p[i + 1]))

                spur = self._astar_blocked(
                    spur_node, destination, weight_fn, blocked_edges, blocked_nodes
                )

                if spur["path"] is not None:
                    candidate = {"path": root_path[:-1] + spur["path"],
                                 "distance": root_cost + spur["distance"]}
                    if not any(c["path"] == candidate["path"] for c in B):
                        B.append(candidate)

            if not B:
                break

            B.sort(key=lambda x: x["distance"])
            A.append(B.pop(0))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        for route in A:
            route["time_ms"] = elapsed_ms
        return A

    def _astar_blocked(self, origin: int, destination: int,
                       weight_fn: Optional[Callable],
                       blocked_edges: set, blocked_nodes: set) -> Dict:
        if weight_fn is not None and getattr(weight_fn, "requires_prev_node", False):
            return self._predecessor_search(
                origin,
                destination,
                weight_fn,
                blocked_edges=blocked_edges,
                blocked_nodes=blocked_nodes,
            )
        t0 = time.perf_counter()
        g: Dict[int, float] = {origin: 0.0}
        came_from: Dict[int, int] = {}
        heap = [(self._haversine(origin, destination), 0.0, origin)]
        closed: set = set()
        nodes_explored = 0

        while heap:
            _, _, u = heapq.heappop(heap)
            if u in closed or u in blocked_nodes:
                continue
            closed.add(u)
            nodes_explored += 1
            if u == destination:
                break
            for v in self.graph.successors(u):
                if v in blocked_nodes or (u, v) in blocked_edges:
                    continue
                ng = g[u] + self._edge_weight(u, v, weight_fn)
                if ng < g.get(v, float("inf")):
                    g[v] = ng
                    came_from[v] = u
                    heapq.heappush(heap, (ng + self._haversine(v, destination), ng, v))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if destination not in g:
            return {"path": None, "distance": float("inf"),
                    "time_ms": elapsed_ms, "nodes_explored": nodes_explored}
        return {"path": self._reconstruct(came_from, origin, destination),
                "distance": g[destination],
                "time_ms": elapsed_ms, "nodes_explored": nodes_explored}

    def benchmark(self, origin: int, destination: int,
                  weight_fn: Optional[Callable] = None) -> Dict:
        results: Dict = {}
        for name, fn in [("dijkstra", self.dijkstra),
                         ("astar", self.astar),
                         ("bidirectional_astar", self.bidirectional_astar)]:
            r = fn(origin, destination, weight_fn)
            results[name] = {
                "time_ms": round(r["time_ms"], 3),
                "distance": round(r["distance"], 2) if r["distance"] != float("inf") else None,
                "nodes_explored": r.get("nodes_explored", 0),
                "path_length": len(r["path"]) if r["path"] else 0,
            }

        k_routes = self.yen_k_shortest(origin, destination, k=3, weight_fn=weight_fn)
        results["yen_k_shortest"] = {
            "time_ms": round(k_routes[0]["time_ms"], 3) if k_routes else 0.0,
            "paths_found": len(k_routes),
            "distances": [round(r["distance"], 2) for r in k_routes],
        }
        return results

    def reweight_edges(self, cost_fn: Callable) -> None:
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            data["_dyn_weight"] = cost_fn(u, v, data)
