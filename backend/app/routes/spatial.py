import logging

import osmnx as ox
from flask import Blueprint, jsonify, request

from app import cache as redis_cache
from app.models import db
from route_optimizer.graph import spatial_queries
from route_optimizer.optimizer import RouteOptimizer
from route_optimizer.utils.helpers import haversine_distance_m

logger = logging.getLogger(__name__)

spatial_bp = Blueprint('spatial', __name__)

_MAX_RADIUS_M = 50_000
_ROUTE_TYPES = ('shortest', 'fuel', 'green', 'avoid_main')


class _BadRequest(ValueError):
    pass


@spatial_bp.errorhandler(_BadRequest)
def _handle_bad_request(exc):
    return jsonify({'error': str(exc)}), 400


def _spatial_supported():
    return db.engine.dialect.name == 'postgresql'


def _unsupported():
    return jsonify({
        'error': 'Spatial queries require a PostgreSQL/PostGIS database'
    }), 503


def _float_arg(name, low, high):
    raw = request.args.get(name)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise _BadRequest(f'{name} must be a number')
    if not low <= value <= high:
        raise _BadRequest(f'{name} must be between {low} and {high}')
    return value


def _geocode(place):
    cached = redis_cache.get(redis_cache.geocode_key(place))
    if cached:
        return float(cached[0]), float(cached[1])
    lat, lon = ox.geocode(place)
    redis_cache.set(redis_cache.geocode_key(place), [lat, lon], ttl=86400)
    return float(lat), float(lon)


def _geocode_or_400(place):
    try:
        return _geocode(place)
    except Exception as exc:
        logger.warning('Geocoding failed for %s: %s', place, exc)
        raise _BadRequest(f'Could not find location: {place}')


def _point():
    """lat/lon from query params, or from a place name via geocoding."""
    place = (request.args.get('place') or '').strip()
    if place:
        return _geocode_or_400(place)
    return _float_arg('lat', -90, 90), _float_arg('lon', -180, 180)


def _radius(default):
    if 'radius_m' not in request.args:
        return default
    return _float_arg('radius_m', 1, _MAX_RADIUS_M)


@spatial_bp.route('/nearby', methods=['GET'])
def nearby():
    """Hospitals/schools/colleges... near a point or a named place, with distance."""
    if not _spatial_supported():
        return _unsupported()
    lat, lon = _point()
    radius_m = _radius(3000)
    category = request.args.get('category')
    if category and category not in spatial_queries.POI_CATEGORIES:
        raise _BadRequest(
            'category must be one of: ' + ', '.join(spatial_queries.POI_CATEGORIES)
        )
    limit = int(_float_arg('limit', 1, 100)) if 'limit' in request.args else 20

    items = spatial_queries.nearby_pois(
        db.engine, lat, lon, radius_m, category=category, limit=limit
    )
    return jsonify({
        'success': True,
        'center': {'lat': lat, 'lon': lon},
        'radius_m': radius_m,
        'count': len(items),
        'items': items,
    }), 200


@spatial_bp.route('/adjacent-roads', methods=['GET'])
def adjacent_roads():
    """Road segments that touch the road nearest to a point."""
    if not _spatial_supported():
        return _unsupported()
    lat, lon = _point()

    result = spatial_queries.adjacent_roads(db.engine, lat, lon)
    if result is None:
        return jsonify({'error': 'No road found near that point'}), 404
    return jsonify({'success': True, **result}), 200


@spatial_bp.route('/summary', methods=['GET'])
def summary():
    """Counts of POIs and road length by type inside a radius, plus the buffer."""
    if not _spatial_supported():
        return _unsupported()
    lat, lon = _point()
    radius_m = _radius(2000)

    result = spatial_queries.area_summary(db.engine, lat, lon, radius_m)
    return jsonify({
        'success': True,
        'center': {'lat': lat, 'lon': lon},
        'radius_m': radius_m,
        **result,
    }), 200


@spatial_bp.route('/distance', methods=['GET'])
def distance():
    """Straight-line (geodesic) distance between two named places.

    Works without PostGIS. For road distance use /api/route/calculate.
    """
    names = [(request.args.get(k) or '').strip() for k in ('from', 'to')]
    if not all(names):
        raise _BadRequest("'from' and 'to' are required")
    (lat1, lon1), (lat2, lon2) = [_geocode_or_400(name) for name in names]

    meters = haversine_distance_m(lat1, lon1, lat2, lon2)
    return jsonify({
        'success': True,
        'from': {'name': names[0], 'lat': lat1, 'lon': lon1},
        'to': {'name': names[1], 'lat': lat2, 'lon': lon2},
        'distance_m': round(meters, 1),
        'distance_km': round(meters / 1000, 2),
        'line': {
            'type': 'LineString',
            'coordinates': [[lon1, lat1], [lon2, lat2]],
        },
    }), 200


def _compute_route(origin, destination, route_type):
    """Route between two (lat, lon) points on a corridor graph; returns the
    result dict plus the path as (lon, lat) pairs."""
    mid = ((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2)
    trip_m = haversine_distance_m(*origin, *destination)
    optimizer = RouteOptimizer()
    optimizer.load_graph(
        center_point=mid, radius_m=max(int(trip_m * 1.5), 3000),
        route_points=[origin, destination],
    )
    result = optimizer.find_route(origin, destination, route_type, 'car')
    nodes = optimizer.graph.nodes
    path = [(nodes[n]['x'], nodes[n]['y']) for n in result['path']]
    return result, path


@spatial_bp.route('/along-route', methods=['GET'])
def along_route():
    """Places (hospitals, fuel stations...) within a distance of the route
    between two named places, in the order you pass them."""
    if not _spatial_supported():
        return _unsupported()
    names = [(request.args.get(k) or '').strip() for k in ('origin', 'destination')]
    if not all(names):
        raise _BadRequest("'origin' and 'destination' are required")
    distance_m = _float_arg('distance_m', 50, 5000) if 'distance_m' in request.args else 500.0
    category = request.args.get('category')
    if category and category not in spatial_queries.POI_CATEGORIES:
        raise _BadRequest(
            'category must be one of: ' + ', '.join(spatial_queries.POI_CATEGORIES)
        )
    route_type = request.args.get('route_type', 'shortest')
    if route_type not in _ROUTE_TYPES:
        raise _BadRequest('route_type must be one of: ' + ', '.join(_ROUTE_TYPES))
    origin, destination = [_geocode_or_400(name) for name in names]

    try:
        result, path = _compute_route(origin, destination, route_type)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404

    items = spatial_queries.places_along_route(
        db.engine, path, distance_m, category=category
    )
    return jsonify({
        'success': True,
        'origin': {'name': names[0], 'lat': origin[0], 'lon': origin[1]},
        'destination': {'name': names[1], 'lat': destination[0], 'lon': destination[1]},
        'route': {
            'distance_m': result['distance_m'],
            'estimated_time_min': result['estimated_time_min'],
            'path': [[lat, lon] for lon, lat in path],
        },
        'distance_m': distance_m,
        'count': len(items),
        'items': items,
    }), 200


def _parse_points(name, low, high):
    """'lat,lon;lat,lon;...' query parameter -> [(lat, lon), ...]."""
    raw = (request.args.get(name) or '').strip()
    points = []
    for part in filter(None, (chunk.strip() for chunk in raw.split(';'))):
        try:
            lat_text, lon_text = part.split(',')
            lat, lon = float(lat_text), float(lon_text)
        except ValueError:
            raise _BadRequest(f"{name} must look like 'lat,lon;lat,lon'")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise _BadRequest(f'{name} has a coordinate out of range')
        points.append((lat, lon))
    if not low <= len(points) <= high:
        raise _BadRequest(f'{name} needs between {low} and {high} points')
    return points


def _category_arg():
    category = request.args.get('category')
    if category and category not in spatial_queries.POI_CATEGORIES:
        raise _BadRequest(
            'category must be one of: ' + ', '.join(spatial_queries.POI_CATEGORIES)
        )
    return category


_MAX_AREA_KM2 = 500.0


@spatial_bp.route('/within-area', methods=['GET'])
def within_area():
    """Places inside a polygon, plus its area and most central place."""
    if not _spatial_supported():
        return _unsupported()
    points = _parse_points('polygon', 3, 50)
    category = _category_arg()

    result = spatial_queries.places_in_area(
        db.engine, [(lon, lat) for lat, lon in points], category=category
    )
    if result is None:
        raise _BadRequest('polygon must not cross itself')
    if result['area_km2'] > _MAX_AREA_KM2:
        raise _BadRequest(f'polygon is too large (limit {_MAX_AREA_KM2:.0f} km2)')
    return jsonify({
        'success': True, 'count': len(result['items']), **result,
    }), 200


@spatial_bp.route('/compare-areas', methods=['GET'])
def compare_areas():
    """Union, overlap and symmetric difference of two circles."""
    if not _spatial_supported():
        return _unsupported()
    circles = []
    for tag in ('1', '2'):
        lat = _float_arg(f'lat{tag}', -90, 90)
        lon = _float_arg(f'lon{tag}', -180, 180)
        radius = _float_arg(f'radius{tag}_m', 1, _MAX_RADIUS_M)
        circles.append((lat, lon, radius))

    result = spatial_queries.compare_areas(db.engine, circles[0], circles[1])
    return jsonify({'success': True, **result}), 200


@spatial_bp.route('/nearest-each', methods=['GET'])
def nearest_each():
    """For each point, the nearest place (k-NN join)."""
    if not _spatial_supported():
        return _unsupported()
    points = _parse_points('points', 1, 10)
    category = _category_arg()

    items = spatial_queries.nearest_place_to_each(db.engine, points, category=category)
    return jsonify({'success': True, 'count': len(items), 'items': items}), 200
