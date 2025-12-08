from flask import Blueprint, request, jsonify, session
from .models import add_user, authenticate_user, get_user_role

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if add_user(username, password, role):
        return jsonify({'success': True, 'message': 'User registered'}), 200
    else:
        return jsonify({'error': 'Username already exists'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = authenticate_user(username, password)
    if user:
        session['username'] = username
        session['role'] = user.role
        return jsonify({'success': True, 'role': user.role}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})

@auth_bp.route('/me', methods=['GET'])
def me():
    username = session.get('username')
    role = session.get('role')
    if username:
        return jsonify({'logged_in': True, 'username': username, 'role': role}), 200
    else:
        return jsonify({'logged_in': False}), 200
