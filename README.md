# MargaMetis — Intelligent Route Optimizer

Real-world road network routing on OpenStreetMap data with custom-built pathfinding algorithms, dynamic cost functions, LLM constraint extraction, and Redis caching.

**Live demo** → [marga-metis.vercel.app](https://marga-metis.vercel.app)

## Algorithm Benchmark

**Real Chennai graph — 50,727 nodes, 129,181 edges** (Chennai Central Railway Station → T Nagar, live OSM data)

| Algorithm | Query time | Nodes explored |
|---|---|---|
| Dijkstra | 94.2 ms | 18,533 |
| A\* (Haversine heuristic) | **17.5 ms** | 2,414 — **7.7× fewer** |
| Bidirectional A\* | **8.9 ms** | 1,264 — **14.7× fewer** |
| Yen's K-Shortest (k=3) | 568 ms | 3 diverse paths |

All four algorithms are implemented from scratch — no `nx.astar_path` or library shortcuts. All four agree on the shortest-path distance (8,756.99 m) — only the search strategy differs.

Measured, not hand-typed: reproduce it yourself with `python scripts/run_benchmark.py`, or read the raw output in [`benchmarks/results_20260811T055459Z.json`](benchmarks/results_20260811T055459Z.json). `tests/e2e/test_benchmark_e2e.py` asserts the structural claim (bidirectional A* never explores more nodes than Dijkstra) on every e2e run, against a live graph.

## Architecture

```
React + Leaflet
      │
      ▼
Flask REST API  ──→  Redis  (geocode cache 24h, route cache 1h)
      │
      ▼
RouteOptimizer
  ├── GraphManager          — OSMnx graph download + GraphML disk cache
  └── route_optimizer/intelligence/
        ├── graph_engine.py     — Dijkstra / A* / Bidirectional A* / Yen's K-Shortest
        ├── cost_function.py    — (u, v, data) → float callable, injected at traversal
        ├── constraint_engine.py — Groq LLaMA 3 (via LiteLLM) NL → structured constraint JSON
        └── route_ranker.py     — multi-criteria scoring + one-sentence explanation
      │
      ▼
PostgreSQL  (user accounts, search history)
```

## Route optimisation modes

Each mode generates a cost function `(u, v, data) → float` based on real OSM `highway` tags:

| Mode | What changes |
|---|---|
| Shortest distance | Minimises `edge.length` |
| Fuel efficient | Penalises roads far from ~80 km/h optimal speed |
| Eco / Green | Fuel efficiency + prefers residential/scenic roads |
| Avoid main roads | 5× penalty on motorway/trunk/primary |
| **Smart (NL)** | Groq LLaMA 3 extracts priorities → dynamic cost weights |

### Smart route

Type a natural-language description — *"scenic route avoiding busy roads"* or *"fastest route via Tambaram"* — and the backend:

1. Sends the query to Groq LLaMA 3 (`llama-3.1-8b-instant`) with few-shot examples
2. Gets back structured JSON: priorities, avoid list, prefer list, waypoints, weights
3. Builds a `(u, v, data) → float` cost function from those weights
4. Runs A* with the cost function injected at traversal time
5. Scores the result across 6 dimensions and generates a one-sentence explanation

Falls back to rule-based extraction when no API key is set.

## Redis caching

- **Geocoding** — place name → (lat, lon) cached 24 h → eliminates Nominatim API calls
- **Route results** — full response cached 1 h → **4,807.7 ms → 8.3 ms** on a repeat query (**576×** faster), measured via `scripts/run_benchmark.py` against a real cache miss (fresh geocode + on-disk GraphML load + routing) vs. a real cache hit — see [`benchmarks/results_20260811T055459Z.json`](benchmarks/results_20260811T055459Z.json)

## Running locally

```bash
# optional: add free Groq key for NL constraint extraction
echo "GROQ_API_KEY=gsk_..." > .env

docker compose up -d
# → http://localhost:3030
```

First search downloads the OSMnx graph (~20 s). All subsequent searches use the GraphML cache on disk and Redis route cache.

## Stack

| | Local | Production |
|---|---|---|
| Frontend | React 18, Vite, React-Leaflet, Tailwind CSS | Vercel |
| Backend | Flask 3, SQLAlchemy, OSMnx 2, NetworkX 3, Gunicorn | Railway |
| Cache | Redis 7 | Railway Redis |
| Database | MySQL 8 | Railway PostgreSQL |
| Deployment | Docker Compose — 4 services | Railway + Vercel |

## Tests

Five layers, `tests/unit` → `tests/e2e`:

| Layer | What it covers | Needs |
|---|---|---|
| `tests/unit` | Pathfinding algorithms, cost function, NL rule-based fallback, confidence scorer, route ranker, cache key logic | Nothing — pure logic, synthetic graphs |
| `tests/smoke` | App factory wires up, blueprints register, `/api/health` responds | Nothing |
| `tests/integration` | Full request → response cycle against a synthetic graph (sqlite DB, real Redis if reachable) | Nothing required; Redis-dependent tests self-skip if unreachable |
| `tests/spec` | JSON-Schema conformance of `/route/calculate`, `/route/smart`, `/route/benchmark`, `/health` responses (`tests/spec/schemas.py` is the closest thing to an OpenAPI spec this repo has) | Nothing |
| `tests/e2e` | Real Flask + real Redis + real OSM data end-to-end, incl. the algorithm-benchmark endpoint's structural invariants | Internet access, Redis running |

```bash
pytest -m "not e2e" -v   # fast, fully offline subset (~110 tests, a few seconds)
pytest -m e2e -v         # real network + Redis, downloads a live Chennai graph on first run
pytest -v                # everything
```

## Project structure

```
MargaMetis/
├── route_optimizer/
│   ├── intelligence/
│   │   ├── graph_engine.py      ← A* / Dijkstra / BiDir-A* / Yen's
│   │   ├── cost_function.py     ← dynamic cost callable
│   │   ├── constraint_engine.py ← Groq LLM + rule-based fallback
│   │   └── route_ranker.py      ← label + explanation
│   ├── graph/manager.py         ← OSMnx + GraphML cache
│   └── optimizer.py
├── backend/
│   └── app/
│       ├── routes/route_api.py  ← /calculate  /smart  /benchmark  /geocode
│       ├── models.py            ← User, SearchHistory
│       └── cache.py             ← Redis layer
├── frontend/src/
│   ├── pages/HomePage.jsx
│   └── components/
├── tests/
│   ├── unit/ smoke/ integration/ spec/ e2e/
│   └── conftest.py               ← shared fixtures (synthetic graph, Flask client, Redis check)
├── scripts/run_benchmark.py      ← regenerates benchmarks/results_*.json (the numbers above)
├── benchmarks/results_*.json
├── docker-compose.yml
└── render.yaml / railway.toml
```
