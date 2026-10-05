import logging

import osmnx as ox
from flask import Blueprint, jsonify, request

from app import cache as redis_cache
from app.models import db
from route_optimizer.graph import spatial_queries
from route_optimizer.utils.helpers import haversine_distance_m

logger = logging.getLogger(__name__)

spatial_bp = Blueprint('spatial', __name__)

_MAX_RADIUS_M = 50_000


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
