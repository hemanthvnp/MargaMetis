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
  ├── GraphManager          — PostGIS spatial graph reads + OSMnx/GraphML fallback
  └── route_optimizer/intelligence/
        ├── graph_engine.py     — Dijkstra / A* / Bidirectional A* / Yen's K-Shortest
        ├── cost_function.py    — (u, v, data) → float callable, injected at traversal
        ├── constraint_engine.py — Groq LLaMA 3 (via LiteLLM) NL → structured constraint JSON
        └── route_ranker.py     — multi-criteria scoring + one-sentence explanation
      │
      ▼
PostgreSQL + PostGIS  (user accounts, search history, spatial road network)
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

docker compose up --build
# → http://localhost:3030           the app
# → http://localhost:3030/spatial   the Spatial Explorer
```

That single command builds and starts PostGIS, Redis, the backend and the frontend, then a one-shot `seed` container loads the Chennai road network and nearby places (hospitals, schools, ...) into the database. The first run takes a few minutes; later runs start in seconds because the data lives in a Docker volume and the seed step skips what is already there. Re-run just the seed with `docker compose run --rm seed`.

If a host port is already taken, move it: `BACKEND_PORT=5055 FRONTEND_PORT=3031 docker compose up --build`. To make an account an admin (registration cannot): `docker compose exec postgres psql -U margametis -d margametis -c "UPDATE users SET role='admin' WHERE username='YOU';"`, then sign out and in.

The local Compose database is PostGIS. The backend applies Alembic migrations before Gunicorn starts. A direct non-Docker development run defaults to SQLite; SQLite supports non-spatial features and continues to load/download OSMnx GraphML graphs, while PostGIS-only spatial queries and analytics are unavailable.

### Database migrations

From `backend/`, apply schema migrations with:

```bash
flask --app wsgi db upgrade
```

To generate a migration after changing SQLAlchemy models:

```bash
flask --app wsgi db migrate -m "describe schema change"
flask --app wsgi db upgrade
```

For an already-deployed database that has the pre-Alembic application schema, stamp the baseline once before the first upgraded deployment. Stamping records the existing schema version without recreating tables:

```bash
flask --app wsgi db stamp 20261005_0001
```

Do this only after confirming that the deployed tables match the baseline migration. New or empty databases should use `db upgrade` instead.

### Spatial road network

The PostGIS road store contains `osm_nodes` and `osm_edges`, with point/line geometries in SRID 4326, GiST geometry indexes, and btree topology indexes. Graph requests use a spatial bounding-box filter plus geography-distance filtering, then construct a request graph with OSM edge tags restored from `attrs`. Nearest-node lookup uses PostGIS geography `<->` ordering, restricted to nodes in the request graph, so the distance ordering is metric and respects longitude/latitude scale. Search history stores spatial origin/destination points with GiST indexes, backfilled from existing result coordinates; the admin spatial-analytics endpoint returns K-means cluster centers and heatmap-ready `[lat, lon, weight]` triples. When an area is missing, the backend uses an existing GraphML cache or the normal OSMnx/Overpass download path and persists the graph to PostGIS; PostGIS requests do not create one GraphML file per request.

To seed the database from the baked Chennai graph and all cached graphs, first apply migrations, then run from the repository root:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://margametis:<password>@localhost:5432/margametis"
python scripts/ingest_graphs.py
```

The ingestion is safe to rerun: OSM node IDs and `(u, v, key)` edges use `ON CONFLICT DO NOTHING`. If `chennai_central.graphml` is not present, the script reports that and ingests any `graph_cache/*.graphml` files it finds; it exits with an error if no graph inputs are available. Pass repeated `--graph <path>` options to ingest specific GraphML files.

## Stack

| | Local | Production |
|---|---|---|
| Frontend | React 18, Vite, React-Leaflet, Tailwind CSS | Vercel |
| Backend | Flask 3, SQLAlchemy, OSMnx 2, NetworkX 3, Gunicorn | Render |
| Cache | Redis 7 | Render Redis |
| Database | PostGIS 16 | Render PostgreSQL |
| Deployment | Docker Compose — 4 services | Render + Vercel |

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
│   ├── graph/manager.py         ← PostGIS spatial reads + download/cache fallback
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
├── scripts/ingest_graphs.py     ← idempotent GraphML → PostGIS import
├── benchmarks/results_*.json
├── docker-compose.yml
└── render.yaml / railway.toml
```
