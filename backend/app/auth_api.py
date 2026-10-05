import secrets
import logging
from flask import Blueprint, request, jsonify, session

from app import cache as redis_cache
from .models import add_user, authenticate_user

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


def _csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def _rate_limit_exceeded(key_prefix: str, limit: int = 5, window_seconds: int = 60) -> bool:
    r = redis_cache._redis()
    if r is None:
        raise RuntimeError('Authentication rate limiter is unavailable')
    bucket = f"auth:{key_prefix}:{request.remote_addr or 'unknown'}"
    try:
        count = r.incr(bucket)
        if count == 1 and not r.expire(bucket, window_seconds):
            raise RuntimeError('Could not set authentication rate-limit window')
        return count > limit
    except Exception as exc:
        logger.exception('Authentication rate limiting failed')
        raise RuntimeError('Authentication rate limiter failed') from exc


def _rate_limit_response(key_prefix: str):
    try:
        if _rate_limit_exceeded(key_prefix):
            label = 'registration' if key_prefix == 'register' else 'login'
            return jsonify({
                'error': f'Too many {label} attempts. Please wait a moment.'
            }), 429
    except RuntimeError:
        return jsonify({'error': 'Authentication rate limiter is unavailable'}), 503
    return None


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    rate_limit_response = _rate_limit_response('register')
    if rate_limit_response:
        return rate_limit_response

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

    rate_limit_response = _rate_limit_response('login')
    if rate_limit_response:
        return rate_limit_response

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