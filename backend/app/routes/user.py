from flask import Blueprint, jsonify, session, request
from sqlalchemy import and_, desc
from app.models import db, User, SearchHistory

user_bp = Blueprint('user', __name__)


def require_login():
    return session.get('username') is not None


def current_user():
    username = session.get('username')
    if not username:
        return None
    return User.query.filter_by(username=username).first()


@user_bp.route('/history', methods=['GET'])
def list_history():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 401
    user = current_user()
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))

    q = (SearchHistory.query
         .filter(SearchHistory.user_id == user.id)
         .order_by(desc(SearchHistory.created_at)))

    items = q.limit(page_size).offset((page - 1) * page_size).all()
    total = q.count()

    data = []
    for it in items:
        data.append({
            'id': it.id,
            'origin': it.origin,
            'destination': it.destination,
            'route_type': it.route_type,
            'vehicle_type': it.vehicle_type,
            'distance_m': it.distance_m,
            'estimated_time_min': it.estimated_time_min,
            'created_at': it.created_at.isoformat(),
        })

    return jsonify({'success': True, 'items': data, 'total': total, 'page': page, 'page_size': page_size})


@user_bp.route('/history/<int:history_id>', methods=['GET'])
def get_history(history_id):
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 401
    user = current_user()
    it = SearchHistory.query.filter(and_(SearchHistory.id == history_id, SearchHistory.user_id == user.id)).first()
    if not it:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'success': True, 'result': it.result_json})


@user_bp.route('/history/query', methods=['GET'])
def query_history():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 401
    user = current_user()
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    route_type = request.args.get('route_type')
    vehicle_type = request.args.get('vehicle_type')

    if not origin or not destination:
        return jsonify({'error': 'origin and destination required'}), 400

    q = (SearchHistory.query
         .filter(and_(
             SearchHistory.user_id == user.id,
             SearchHistory.origin == origin,
             SearchHistory.destination == destination,
             (SearchHistory.route_type == route_type) if route_type else True,
             (SearchHistory.vehicle_type == vehicle_type) if vehicle_type else True,
         ))
         .order_by(desc(SearchHistory.created_at))
         .first())

    if not q:
        return jsonify({'error': 'No cached result'}), 404

    return jsonify({'success': True, 'result': q.result_json})
