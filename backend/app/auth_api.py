import secrets
from flask import Blueprint, request, jsonify, session

from app import cache as redis_cache
from .models import add_user, authenticate_user

auth_bp = Blueprint('auth', __name__)


def _csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def _csrf_is_valid(payload: dict | None) -> bool:
    if not request.headers.get('Origin'):
        return True
    token = (payload or {}).get('csrf_token') or request.headers.get('X-CSRFToken')
    if not token:
        return False
    return secrets.compare_digest(str(session.get('_csrf_token', '')), str(token))


def _rate_limit_exceeded(key_prefix: str, limit: int = 5, window_seconds: int = 60) -> bool:
    r = redis_cache._redis()
    if r is None:
        return False
    bucket = f"auth:{key_prefix}:{request.remote_addr or 'unknown'}"
    try:
        now = int(__import__('time').time())
        pipe = r.pipeline()
        pipe.incr(bucket)
        pipe.expire(bucket, window_seconds)
        result = pipe.execute()
        return result[0] > limit
    except Exception:
        return False


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    if _rate_limit_exceeded('register'):
        return jsonify({'error': 'Too many registration attempts. Please wait a moment.'}), 429
    if request.headers.get('Origin') and not _csrf_is_valid(data):
        return jsonify({'error': 'CSRF validation failed'}), 403

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if add_user(username, password, role='user'):
        session['_csrf_token'] = _csrf_token()
        return jsonify({
            'success': True,
            'message': 'User registered',
            'csrf_token': session.get('_csrf_token')
        }), 200

    return jsonify({'error': 'Username already exists'}), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}

    if _rate_limit_exceeded('login'):
        return jsonify({'error': 'Too many login attempts. Please wait a moment.'}), 429
    if request.headers.get('Origin') and not _csrf_is_valid(data):
        return jsonify({'error': 'CSRF validation failed'}), 403

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = authenticate_user(username, password)

    if user:
        session['username'] = user.username
        session['role'] = user.role
        session['_csrf_token'] = _csrf_token()

        return jsonify({
            'success': True,
            'role': user.role,
            'csrf_token': session.get('_csrf_token')
        }), 200

    return jsonify({'error': 'Invalid credentials'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    if request.headers.get('Origin') and not _csrf_is_valid(request.get_json(silent=True) or {}):
        return jsonify({'error': 'CSRF validation failed'}), 403
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out'
    }), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    username = session.get('username')
    role = session.get('role')

    if username:
        return jsonify({
            'logged_in': True,
            'username': username,
            'role': role,
            'csrf_token': _csrf_token()
        }), 200

    return jsonify({
        'logged_in': False,
        'csrf_token': _csrf_token()
    }), 200