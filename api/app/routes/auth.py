"""
Authentication Blueprint for InfraTick.
Handles registration and login using JWT.
"""

from functools import wraps
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash
import jwt
import datetime
from ..models import create_user, get_user_by_email, get_user_by_id, add_audit_log
from ..config import Config

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

def token_required(f):
    """Decorator to protect routes — extracts current user from JWT."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'message': 'Authorization token is missing or invalid!'}), 401
        
        try:
            token = token.split(" ")[1]
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            current_user = get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({'message': 'User session invalid!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except Exception:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.json
    full_name = data.get('fullName')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'member')

    if not all([full_name, email, password]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    user = create_user(full_name, email, password, role)
    if user:
        return jsonify({'success': True, 'message': 'User registered successfully!'}), 201
    else:
        return jsonify({'success': False, 'message': 'Email already registered!'}), 409

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = get_user_by_email(email)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, Config.SECRET_KEY, algorithm="HS256")

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'fullName': user['full_name'],
            'email': user['email'],
            'role': user['role']
        }
    }), 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({
        'success': True,
        'user': {
            'id': current_user['id'],
            'full_name': current_user['full_name'],
            'email': current_user['email'],
            'role': current_user['role']
        }
    })
