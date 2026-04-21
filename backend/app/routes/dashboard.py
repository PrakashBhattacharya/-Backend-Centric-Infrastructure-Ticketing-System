"""
Dashboard API blueprint — real aggregated data from the database.
"""

from flask import Blueprint, jsonify
from datetime import datetime
import psycopg2
from .auth import token_required
from ..models import get_member_stats, get_engineer_stats, get_admin_stats, get_audit_logs
from ..config import Config

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

@dashboard_bp.route('/admin/diag', methods=['GET'])
@token_required
def admin_diag(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    diag_results = {
        'timestamp': datetime.utcnow().isoformat(),
        'env_config': {
            'has_postgres_url': bool(Config.POSTGRES_URL),
            'postgres_url_start': Config.POSTGRES_URL[:15] + '...' if Config.POSTGRES_URL else None
        },
        'connection_test': 'Not Started',
        'query_test': 'Not Started',
        'error': None
    }

    try:
        # Test basic connection
        conn = psycopg2.connect(Config.POSTGRES_URL)
        diag_results['connection_test'] = 'Passed'
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        diag_results['query_test'] = 'Basic SELECT Passed'
        
        cursor.execute("SELECT COUNT(*) FROM tickets")
        count = cursor.fetchone()[0]
        diag_results['ticket_count'] = count
        
        cursor.close()
        conn.close()
    except Exception as e:
        diag_results['error'] = str(e)
        diag_results['connection_test'] = 'Failed'

    return jsonify(diag_results)

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
        created_at = log['created_at']
        # PostgreSQL returns a datetime object; SQLite returns a string
        if isinstance(created_at, str):
            dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        else:
            dt = created_at
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
