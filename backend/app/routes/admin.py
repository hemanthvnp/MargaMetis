from flask import Blueprint, jsonify, request, session
from sqlalchemy import func, extract, text
from app.models import db, SearchHistory

admin_bp = Blueprint('admin', __name__)


def require_admin():
    return session.get('role') == 'admin'


def _spatial_analytics_supported():
    return db.engine.dialect.name == 'postgresql'


@admin_bp.route('/stats', methods=['GET'])
def stats():
    if not require_admin():
        return jsonify({'error': 'Forbidden'}), 403

    total_searches = db.session.query(func.count(SearchHistory.id)).scalar() or 0
    unique_users   = db.session.query(func.count(func.distinct(SearchHistory.user_id))).scalar() or 0

    top_origins = [
        {'origin': o, 'count': c}
        for o, c in (
            db.session.query(SearchHistory.origin, func.count(SearchHistory.id).label('count'))
            .group_by(SearchHistory.origin)
            .order_by(func.count(SearchHistory.id).desc())
            .limit(10).all()
        )
    ]

    top_destinations = [
        {'destination': d, 'count': c}
        for d, c in (
            db.session.query(SearchHistory.destination, func.count(SearchHistory.id).label('count'))
            .group_by(SearchHistory.destination)
            .order_by(func.count(SearchHistory.id).desc())
            .limit(10).all()
        )
    ]

    top_route_types = [
        {'route_type': rt, 'count': c}
        for rt, c in (
            db.session.query(SearchHistory.route_type, func.count(SearchHistory.id).label('count'))
            .group_by(SearchHistory.route_type)
            .order_by(func.count(SearchHistory.id).desc())
            .all()
        )
    ]

    top_pairs = [
        {'origin': o, 'destination': d, 'count': c}
        for o, d, c in (
            db.session.query(
                SearchHistory.origin, SearchHistory.destination,
                func.count(SearchHistory.id).label('count')
            )
            .group_by(SearchHistory.origin, SearchHistory.destination)
            .order_by(func.count(SearchHistory.id).desc())
            .limit(10).all()
        )
    ]

    hourly_distribution = [
        {'hour': int(h or 0), 'count': int(c or 0)}
        for h, c in (
            db.session.query(
                extract('hour', SearchHistory.created_at).label('hour'),
                func.count(SearchHistory.id).label('count')
            )
            .group_by(extract('hour', SearchHistory.created_at))
            .order_by(extract('hour', SearchHistory.created_at))
            .all()
        )
    ]

    return jsonify({
        'success': True,
        'totals': {
            'searches':     int(total_searches),
            'unique_users': int(unique_users),
        },
        'top_origins':          top_origins,
        'top_destinations':     top_destinations,
        'top_route_types':      top_route_types,
        'top_pairs':            top_pairs,
        'hourly_distribution':  hourly_distribution,
    }), 200


@admin_bp.route('/spatial-analytics', methods=['GET'])
def spatial_analytics():
    if not require_admin():
        return jsonify({'error': 'Forbidden'}), 403

    try:
        k = int(request.args.get('k', '5'))
    except (TypeError, ValueError):
        return jsonify({'error': 'k must be an integer from 1 to 20'}), 400
    if not 1 <= k <= 20:
        return jsonify({'error': 'k must be an integer from 1 to 20'}), 400
    if not _spatial_analytics_supported():
        return jsonify({
            'error': 'Spatial analytics require a PostgreSQL/PostGIS database'
        }), 503

    cluster_rows = db.session.execute(
        text(
            """
            WITH points AS (
                SELECT 'origin' AS point_type, origin_geom AS geom
                FROM search_history
                WHERE origin_geom IS NOT NULL
                UNION ALL
                SELECT 'destination' AS point_type, dest_geom AS geom
                FROM search_history
                WHERE dest_geom IS NOT NULL
            ),
            clustered AS (
                SELECT point_type, geom,
                       ST_ClusterKMeans(geom, :k)
                           OVER (PARTITION BY point_type) AS cluster_id
                FROM points
            )
            SELECT point_type, cluster_id,
                   ST_Y(ST_Centroid(ST_Collect(geom))) AS lat,
                   ST_X(ST_Centroid(ST_Collect(geom))) AS lon,
                   COUNT(*) AS weight
            FROM clustered
            GROUP BY point_type, cluster_id
            ORDER BY point_type, cluster_id
            """
        ),
        {'k': k},
    ).mappings().all()
    heatmap_rows = db.session.execute(
        text(
            """
            WITH points AS (
                SELECT origin_geom AS geom FROM search_history
                WHERE origin_geom IS NOT NULL
                UNION ALL
                SELECT dest_geom AS geom FROM search_history
                WHERE dest_geom IS NOT NULL
            )
            SELECT ROUND(ST_Y(geom)::numeric, 6) AS lat,
                   ROUND(ST_X(geom)::numeric, 6) AS lon,
                   COUNT(*) AS weight
            FROM points
            GROUP BY ROUND(ST_Y(geom)::numeric, 6),
                     ROUND(ST_X(geom)::numeric, 6)
            ORDER BY weight DESC
            """
        )
    ).mappings().all()

    clusters = {'origins': [], 'destinations': []}
    for row in cluster_rows:
        collection = (
            clusters['origins']
            if row['point_type'] == 'origin'
            else clusters['destinations']
        )
        collection.append({
            'cluster_id': int(row['cluster_id']),
            'lat': float(row['lat']),
            'lon': float(row['lon']),
            'weight': int(row['weight']),
        })
    heatmap = [
        [float(row['lat']), float(row['lon']), int(row['weight'])]
        for row in heatmap_rows
    ]
    return jsonify({
        'success': True,
        'k': k,
        'clusters': clusters,
        'heatmap': heatmap,
    }), 200
