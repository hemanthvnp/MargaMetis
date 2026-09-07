from flask import Blueprint, request, jsonify, session
import logging
import os
import time

import osmnx as ox

from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.utils.helpers import haversine_distance_m
from route_optimizer.intelligence.graph_engine import GraphEngine
from route_optimizer.intelligence.constraint_engine import ConstraintEngine
from route_optimizer.intelligence.cost_function import CostFunctionGenerator
from route_optimizer.intelligence.route_ranker import RouteRanker
from route_optimizer.confidence_scorer import RouteConfidenceScorer
from app.models import db, User, SearchHistory
from app import cache as redis_cache

logger = logging.getLogger(__name__)
route_bp = Blueprint('routes', __name__)

# Global optimizer instance
optimizer = None


def get_optimizer():
    global optimizer
    if optimizer is None:
        optimizer = RouteOptimizer()
    return optimizer


def _save_history(origin, destination, route_type, vehicle_type, payload):
    try:
        db.session.rollback()
        username = session.get('username') or request.headers.get('X-Username')
        user_id = None
        if username:
            user = User.query.filter_by(username=username).first()
            user_id = user.id if user else None
        save_json = {k: v for k, v in payload.items() if k != 'path_coordinates'}
        record = SearchHistory(
            user_id=user_id,
            origin=origin,
            destination=destination,
            route_type=route_type,
            vehicle_type=vehicle_type,
            distance_m=float(payload['distance_m']),
            estimated_time_min=payload.get('estimated_time_min'),
            result_json=save_json,
        )
        db.session.add(record)
        db.session.commit()
        logger.info(f"History saved: user_id={user_id} username={username}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save history: {e}", exc_info=True)


@route_bp.route('/route/calculate', methods=['POST'])
def calculate_route():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        origin = data.get('origin', '').strip()
        destination = data.get('destination', '').strip()
        origin_coords = data.get('origin_coords')
        dest_coords = data.get('dest_coords')
        route_type = data.get('route_type', 'shortest')
        time_of_day = int(data.get('time_of_day', 17))
        vehicle_type = data.get('vehicle_type', 'car')
        
        # Validate inputs
        if not origin or not destination:
            return jsonify({'error': 'Origin and destination are required'}), 400
        
        logger.info(f"Route request: {origin} -> {destination}")
        
        try:
            # ── Geocoding (Redis-cached, TTL 24h) ─────────────────
            if not origin_coords:
                cached = redis_cache.get(redis_cache.geocode_key(origin))
                if cached:
                    origin_coords = tuple(cached)
                    logger.info(f"Geocode cache HIT: {origin}")
                else:
                    origin_coords = ox.geocode(origin)
                    redis_cache.set(redis_cache.geocode_key(origin), list(origin_coords), ttl=86400)
            else:
                origin_coords = tuple(origin_coords)

            if not dest_coords:
                cached = redis_cache.get(redis_cache.geocode_key(destination))
                if cached:
                    dest_coords = tuple(cached)
                    logger.info(f"Geocode cache HIT: {destination}")
                else:
                    dest_coords = ox.geocode(destination)
                    redis_cache.set(redis_cache.geocode_key(destination), list(dest_coords), ttl=86400)
            else:
                dest_coords = tuple(dest_coords)

            # ── Route cache check (Redis, TTL 1h) ─────────────────
            rkey = redis_cache.route_key(origin, destination, route_type, vehicle_type)
            cached_route = redis_cache.get(rkey)
            if cached_route:
                logger.info(f"Route cache HIT: {origin} -> {destination}")
                cached_route['cache_hit'] = True
                _save_history(origin, destination, route_type, vehicle_type, cached_route)
                return jsonify(cached_route), 200

            # ── Compute route ──────────────────────────────────────
            direct_dist = haversine_distance_m(*origin_coords, *dest_coords)
            graph_radius = max(int(direct_dist * 1.5), 3000)
            mid_point = (
                (origin_coords[0] + dest_coords[0]) / 2,
                (origin_coords[1] + dest_coords[1]) / 2,
            )

            optimizer_instance = get_optimizer()
            optimizer_instance.load_graph(center_point=mid_point, radius_m=graph_radius)

            start_time = time.time()
            result = optimizer_instance.find_route(origin_coords, dest_coords, route_type, vehicle_type)
            duration = time.time() - start_time

            path_coords = [
                {'lat': optimizer_instance.graph.nodes[n]['y'],
                 'lon': optimizer_instance.graph.nodes[n]['x']}
                for n in result["path"]
            ]

            _AVG_SPEED = {"car": 40, "bike": 25, "bus": 30, "truck": 25, "auto": 35}
            try:
                scorer = RouteConfidenceScorer(optimizer_instance.graph)
                conf = scorer.score(
                    result["path"],
                    departure_hour=time_of_day,
                    avg_speed_kmh=_AVG_SPEED.get(vehicle_type, 40),
                )
                confidence_data = {
                    "score":      conf.confidence,
                    "risk_level": conf.risk_level,
                    "eta_range":  list(conf.eta_range),
                    "breakdown":  conf.breakdown,
                    "warnings":   conf.warnings,
                }
            except Exception as ce:
                logger.warning(f"Confidence scoring failed: {ce}")
                confidence_data = None

            response_payload = {
                'success':            True,
                'cache_hit':          False,
                'distance_km':        round(result["distance_m"] / 1000, 2),
                'distance_m':         round(result["distance_m"], 2),
                'calculation_time_s': round(duration, 3),
                'algorithm_time_ms':  result.get("algorithm_time_ms"),
                'nodes_explored':     result.get("nodes_explored"),
                'path_nodes':         len(result["path"]),
                'origin':      {'name': origin,      'lat': origin_coords[0], 'lon': origin_coords[1]},
                'destination': {'name': destination,  'lat': dest_coords[0],  'lon': dest_coords[1]},
                'path_coordinates':   path_coords,
                'estimated_time_min': result["estimated_time_min"],
                'route_type':         route_type,
                'vehicle_type':       vehicle_type,
                'confidence':         confidence_data,
            }

            # Store in Redis cache
            redis_cache.set(rkey, response_payload, ttl=3600)

            _save_history(origin, destination, route_type, vehicle_type, response_payload)

            return jsonify(response_payload), 200
            
        except Exception as e:
            logger.error(f"Error during route calculation: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Could not find a route. Please check the locations.',
                'details': str(e)
            }), 400
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


def _load_graph_for_coords(origin_coords, dest_coords, extra_coords=None):
    all_coords = [origin_coords, dest_coords] + (extra_coords or [])
    lats = [c[0] for c in all_coords]
    lons = [c[1] for c in all_coords]
    mid_point = ((max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2)

    # Radius = max distance from centroid to any point × 1.5, minimum 3km
    max_dist = max(haversine_distance_m(mid_point[0], mid_point[1], lat, lon)
                   for lat, lon in zip(lats, lons))
    graph_radius = max(int(max_dist * 1.5), 3000)

    opt = get_optimizer()
    opt.load_graph(center_point=mid_point, radius_m=graph_radius)
    return opt


@route_bp.route('/route/smart', methods=['POST'])
def smart_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        query = data.get("query", "").strip()
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()

        if not origin or not destination:
            return jsonify({"error": "origin and destination are required"}), 400

        # Geocode
        origin_coords = data.get("origin_coords")
        dest_coords = data.get("dest_coords")
        try:
            if not origin_coords:
                origin_coords = ox.geocode(origin)
            else:
                origin_coords = tuple(origin_coords)
            if not dest_coords:
                dest_coords = ox.geocode(destination)
            else:
                dest_coords = tuple(dest_coords)
        except Exception as geo_err:
            return jsonify({"error": f"Geocoding failed: {geo_err}"}), 400

        # Extract constraints from NL query (Groq LLaMA 3 with rule-based fallback)
        api_key = os.environ.get("GROQ_API_KEY")
        constraint_engine = ConstraintEngine(api_key=api_key)
        constraints = constraint_engine.extract_constraints(
            query or f"route from {origin} to {destination}"
        )

        # Override with explicit request fields if provided
        if data.get("vehicle_type"):
            constraints["vehicle_type"] = data["vehicle_type"]
        if data.get("time_of_day") is not None:
            constraints["time_of_day"] = int(data["time_of_day"])

        if constraints.get("clarification_needed") and not (query or "").strip():
            return jsonify({
                "clarification_needed": True,
                "question": constraints["clarification_question"],
                "constraints": constraints,
            }), 200

        # Geocode waypoints first (before loading graph, so graph covers them)
        waypoints = constraints.get("waypoints", [])
        waypoint_coords_list = []
        for wp_name in waypoints:
            try:
                # Try geocoding with origin city context, then plain name
                try:
                    wp_coords = ox.geocode(f"{wp_name}, {origin}")
                except Exception:
                    wp_coords = ox.geocode(wp_name)
                waypoint_coords_list.append(wp_coords)
                logger.info(f"Waypoint '{wp_name}' -> {wp_coords}")
            except Exception as wp_err:
                logger.warning(f"Could not geocode waypoint '{wp_name}': {wp_err}")

        # Load graph covering origin + ALL waypoints + destination
        t0 = time.time()
        try:
            opt = _load_graph_for_coords(origin_coords, dest_coords, waypoint_coords_list)
        except Exception as graph_err:
            return jsonify({"error": f"Graph loading failed: {graph_err}"}), 400

        origin_node = ox.distance.nearest_nodes(opt.graph, origin_coords[1], origin_coords[0])
        dest_node = ox.distance.nearest_nodes(opt.graph, dest_coords[1], dest_coords[0])

        # Build cost function
        cost_fn = CostFunctionGenerator(constraints).generate()
        engine = GraphEngine(opt.graph)

        # Waypoint routing: chain origin → wp1 → wp2 → … → destination
        if waypoint_coords_list:
            wp_nodes = [
                ox.distance.nearest_nodes(opt.graph, wc[1], wc[0])
                for wc in waypoint_coords_list
            ]
            if wp_nodes:
                # Build a single concatenated path through all waypoints
                all_nodes = [origin_node] + wp_nodes + [dest_node]
                combined_path: list = []
                combined_dist: float = 0.0
                ok = True
                for seg_start, seg_end in zip(all_nodes, all_nodes[1:]):
                    seg = engine.astar(seg_start, seg_end, cost_fn)
                    if seg["path"] is None:
                        ok = False
                        break
                    # Avoid duplicate junction node between segments
                    combined_path.extend(seg["path"] if not combined_path else seg["path"][1:])
                    combined_dist += seg["distance"]
                if ok and combined_path:
                    raw = {"path": combined_path, "distance": combined_dist, "time_ms": 0}
                else:
                    logger.warning("Waypoint routing failed, falling back to direct A*")
                    raw = engine.astar(origin_node, dest_node, cost_fn)
            else:
                raw = engine.astar(origin_node, dest_node, cost_fn)
            routes = [raw] if (raw and raw.get("path")) else []
        else:
            # No waypoints — Yen's K-Shortest for up to 3 diverse route options
            try:
                max_routes = max(1, min(int(constraints.get("max_routes", 3) or 3), 3))
            except (TypeError, ValueError):
                max_routes = 3

            routes = engine.yen_k_shortest(origin_node, dest_node, k=max_routes, weight_fn=cost_fn) \
                if max_routes > 1 else []

            if not routes:
                raw = engine.astar(origin_node, dest_node, cost_fn)
                routes = [raw] if (raw and raw.get("path")) else []

        if not routes:
            return jsonify({"error": "No routes found between these locations"}), 400

        # Score, rank, and explain
        ranker = RouteRanker(opt.graph)
        ranked = ranker.rank_routes(routes, constraints)

        # Normalise routes to the frontend schema
        import uuid as _uuid  # noqa: PLC0415

        normalised = []
        for route in ranked:
            s = route.get("scores", {})
            dist = route.get("distance", s.get("total_length_m", 0))

            # ETA — distance / speed with peak-hour multiplier
            _peak = {7, 8, 9, 17, 18, 19, 20}
            _hw_speed = {"motorway": 80, "trunk": 70, "primary": 55, "secondary": 45,
                         "tertiary": 35, "residential": 28, "unclassified": 35, "service": 18}
            _hw = s.get("dominant_highway", "secondary")
            _speed = _hw_speed.get(_hw, 40)
            _tod = constraints.get("time_of_day") or 12
            _base = (dist / 1000 / _speed) * 60
            _base *= 1.4 if _tod in _peak else (1.15 if 10 <= _tod <= 16 else 1.0)
            _base *= 1 + (1 - s.get("safety", 0.5)) * 0.3
            eta = round(max(_base, 0.5), 1)

            # Semantic class heuristic
            _scenic = s.get("scenic", 0.5)
            _cong   = 1 - s.get("safety", 0.5)
            if _scenic > 0.65:
                sem_class, sem_conf = "Scenic", round(0.60 + _scenic * 0.25, 2)
            elif _cong > 0.55:
                sem_class, sem_conf = "Crowded", round(min(0.55 + _cong * 0.35, 0.95), 2)
            else:
                sem_class, sem_conf = "Peaceful", 0.70

            # Fix explanation to use ML eta instead of raw speed_time_min
            explanation = route.get("explanation", "")
            raw_t = f"~{s.get('speed_time_min', 0):.0f} min"
            explanation = explanation.replace(raw_t, f"~{eta:.0f} min")

            # Path coordinates
            coords = [{"lat": opt.graph.nodes[n]["y"], "lon": opt.graph.nodes[n]["x"]}
                      for n in route.get("path", [])]

            normalised.append({
                "route_id": str(_uuid.uuid4())[:8],
                "label": route.get("label", "Route"),
                "rank": route.get("rank", 1),
                "distance_m": round(dist, 1),
                "eta_min": eta,
                "score": {
                    "speed":       round(s.get("speed", 0), 3),
                    "safety":      round(s.get("safety", 0), 3),
                    "scenic":      round(s.get("scenic", 0), 3),
                    "comfort":     round(s.get("comfort", 0), 3),
                    "fuel_access": round(s.get("fuel_access", 0), 3),
                    "toll_cost":   round(s.get("toll_cost", 1), 3),
                    "composite":   round(s.get("composite", 0), 3),
                    "speed_time_min":  round(s.get("speed_time_min", eta), 1),
                    "total_length_m":  round(s.get("total_length_m", dist), 1),
                },
                "semantic_class":      sem_class,
                "semantic_confidence": round(sem_conf, 2),
                "explanation": explanation,
                "path_coordinates": coords,
            })

        elapsed = round(time.time() - t0, 3)

        response_payload = {
            "success": True,
            "routes": normalised,
            "constraints": constraints,
            "cost_formula": CostFunctionGenerator(constraints).describe(),
            "origin": {"name": origin, "lat": origin_coords[0], "lon": origin_coords[1]},
            "destination": {"name": destination, "lat": dest_coords[0], "lon": dest_coords[1]},
            "calculation_time_s": elapsed,
        }

        # Log to search history
        try:
            username = session.get("username")
            user_id = None
            if username:
                user = User.query.filter_by(username=username).first()
                if user:
                    user_id = user.id
            best = normalised[0] if normalised else {}
            record = SearchHistory(
                user_id=user_id,
                origin=origin,
                destination=destination,
                route_type=f"smart:{constraints.get('priorities', [''])[0]}",
                vehicle_type=constraints.get("vehicle_type", "car"),
                distance_m=best.get("distance_m"),
                estimated_time_min=best.get("eta_min"),
                result_json=response_payload,
            )
            db.session.add(record)
            db.session.commit()
        except Exception as log_err:
            logger.warning(f"Failed to log smart route: {log_err}")

        return jsonify(response_payload), 200

    except Exception as exc:
        logger.error(f"smart_route error: {exc}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@route_bp.route('/route/benchmark', methods=['POST'])
def benchmark_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()
        if not origin or not destination:
            return jsonify({"error": "origin and destination are required"}), 400

        origin_coords = data.get("origin_coords")
        dest_coords = data.get("dest_coords")
        try:
            if not origin_coords:
                origin_coords = ox.geocode(origin)
            else:
                origin_coords = tuple(origin_coords)
            if not dest_coords:
                dest_coords = ox.geocode(destination)
            else:
                dest_coords = tuple(dest_coords)
        except Exception as geo_err:
            return jsonify({"error": f"Geocoding failed: {geo_err}"}), 400

        try:
            opt = _load_graph_for_coords(origin_coords, dest_coords)
        except Exception as graph_err:
            return jsonify({"error": f"Graph loading failed: {graph_err}"}), 400

        origin_node = ox.distance.nearest_nodes(opt.graph, origin_coords[1], origin_coords[0])
        dest_node = ox.distance.nearest_nodes(opt.graph, dest_coords[1], dest_coords[0])

        engine = GraphEngine(opt.graph)
        results = engine.benchmark(origin_node, dest_node)

        return jsonify({
            "success": True,
            "origin": {"name": origin, "lat": origin_coords[0], "lon": origin_coords[1]},
            "destination": {"name": destination, "lat": dest_coords[0], "lon": dest_coords[1]},
            "graph_nodes": opt.graph.number_of_nodes(),
            "graph_edges": opt.graph.number_of_edges(),
            "results": results,
        }), 200

    except Exception as exc:
        logger.error(f"benchmark_route error: {exc}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


@route_bp.route('/route/geocode', methods=['POST'])
def geocode_location():
    try:
        data = request.get_json()
        location = data.get('location', '').strip()
        
        if not location:
            return jsonify({'error': 'Location is required'}), 400
        
        logger.info(f"Geocoding: {location}")
        
        try:
            coords = ox.geocode(location)
            return jsonify({
                'success': True,
                'location': location,
                'lat': coords[0],
                'lon': coords[1]
            }), 200
        except Exception as e:
            logger.warning(f"Geocoding failed for {location}: {str(e)}")
            return jsonify({'error': f'Could not find location: {location}'}), 404
    
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred during geocoding'}), 500
