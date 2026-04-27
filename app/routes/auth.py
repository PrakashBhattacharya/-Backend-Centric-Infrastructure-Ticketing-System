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
    from ..models import execute_query
    uid = current_user['id']
    role = current_user['role']

    # Ticket stats vary by role
    if role == 'member':
        total   = (execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s", (uid,), fetchone=True) or {}).get('c', 0)
        open_t  = (execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True) or {}).get('c', 0)
        resolved= (execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True) or {}).get('c', 0)
        stats = {'total_tickets': total, 'open_tickets': open_t, 'resolved_tickets': resolved}
    elif role == 'engineer':
        assigned = (execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True) or {}).get('c', 0)
        resolved = (execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True) or {}).get('c', 0)
        mttr_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as m FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True) or {}
        mttr = round(float(mttr_row.get('m') or 0), 1)
        stats = {'assigned_tickets': assigned, 'resolved_tickets': resolved, 'avg_mttr': f"{mttr}h"}
    else:  # admin
        total   = (execute_query("SELECT COUNT(*) as c FROM tickets", fetchone=True) or {}).get('c', 0)
        open_t  = (execute_query("SELECT COUNT(*) as c FROM tickets WHERE status IN ('Open','In Progress','Pending Approval')", fetchone=True) or {}).get('c', 0)
        resolved= (execute_query("SELECT COUNT(*) as c FROM tickets WHERE status IN ('Resolved','Closed')", fetchone=True) or {}).get('c', 0)
        engineers = (execute_query("SELECT COUNT(*) as c FROM users WHERE role='engineer'", fetchone=True) or {}).get('c', 0)
        members   = (execute_query("SELECT COUNT(*) as c FROM users WHERE role='member'", fetchone=True) or {}).get('c', 0)
        stats = {'total_tickets': total, 'open_tickets': open_t, 'resolved_tickets': resolved, 'engineers': engineers, 'members': members}

    return jsonify({
        'success': True,
        'user': {
            'id': current_user['id'],
            'full_name': current_user['full_name'],
            'email': current_user['email'],
            'role': current_user['role'],
            'created_at': current_user.get('created_at', ''),
            'stats': stats
        }
    })
