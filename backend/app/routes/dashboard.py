"""
Dashboard API blueprint — real aggregated data from the database.
"""

from flask import Blueprint, jsonify
from .auth import token_required
from ..models import get_member_stats, get_engineer_stats, get_admin_stats, get_audit_logs

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/member', methods=['GET'])
@token_required
def member_dashboard(current_user):
    if current_user['role'] != 'member':
        return jsonify({'message': 'Unauthorized access!'}), 403
    stats = get_member_stats(current_user['id'])
    return jsonify({'success': True, **stats})

@dashboard_bp.route('/engineer', methods=['GET'])
@token_required
def engineer_dashboard(current_user):
    if current_user['role'] != 'engineer':
        return jsonify({'message': 'Unauthorized access!'}), 403
    stats = get_engineer_stats(current_user['id'])
    return jsonify({'success': True, **stats})

@dashboard_bp.route('/admin/overview', methods=['GET'])
@token_required
def admin_overview(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized access!'}), 403
    stats = get_admin_stats()
    audit_logs = get_audit_logs(limit=20)
    
    # Process audit logs for dashboard view
    formatted_logs = []
    for log in audit_logs:
        from datetime import datetime
        dt = datetime.strptime(log['created_at'], '%Y-%m-%d %H:%M:%S')
        formatted_logs.append({
            'text': log['action'],
            'time': dt.strftime('%H:%M • %b %d'),
            'icon': log['icon'],
            'color': log['color'],
            'danger': log['danger'] == 1
        })

    return jsonify({
        'success': True,
        **stats,
        'auditLogs': formatted_logs
    })
