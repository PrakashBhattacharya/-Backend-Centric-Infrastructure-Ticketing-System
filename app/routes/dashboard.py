"""
Dashboard API blueprint — real aggregated data from the database.
"""

from flask import Blueprint, jsonify
from datetime import datetime
from .auth import token_required
from ..models import get_member_stats, get_engineer_stats, get_admin_stats, get_audit_logs, get_engineers
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
        'connection_status': 'unknown',
        'tables': {},
        'env_vars': {
            'POSTGRES_URL_FOUND': bool(Config.POSTGRES_URL)
        },
        'error': None
    }

    try:
        from ..models import get_db
        import traceback
        conn = get_db()
        if not conn:
            diag_results['connection_status'] = 'Failed (get_db returned None)'
        else:
            diag_results['connection_status'] = 'Success'
            cursor = conn.cursor()
            
            # Check table counts
            tables_to_check = ['users', 'tickets', 'audit_logs', 'comments']
            for table in tables_to_check:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    diag_results['tables'][table] = count
                except Exception as table_err:
                    diag_results['tables'][table] = f"Error: {str(table_err)}"
                    conn.rollback()
            
            cursor.close()
            conn.close()
    except Exception as e:
        diag_results['error'] = str(e)
        diag_results['traceback'] = traceback.format_exc()

    return jsonify(diag_results)

@dashboard_bp.route('/admin/overview', methods=['GET'])
@token_required
def admin_overview(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized access!'}), 403
    stats = get_admin_stats()
    audit_logs = get_audit_logs(limit=20)
    
    # Format audit logs for dashboard view — frontend expects: text, time, icon, color, danger (bool)
    formatted_logs = []
    for log in audit_logs:
        created_at = log['created_at']
        if isinstance(created_at, str):
            try:
                dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                dt = datetime.utcnow()
        else:
            dt = created_at if created_at else datetime.utcnow()
        formatted_logs.append({
            'text': log['action'],
            'sub': log.get('details', ''),
            'time': dt.strftime('%H:%M • %b %d'),
            'icon': log.get('icon', 'fa-info-circle'),
            'color': log.get('color', '#3b82f6'),
            'danger': log.get('danger', 0) == 1
        })

    return jsonify({
        'success': True,
        **stats,
        'auditLogs': formatted_logs
    })

@dashboard_bp.route('/engineers', methods=['GET'])
@token_required
def list_engineers(current_user):
    """Returns all engineers with their current workload — used by assign modal."""
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized access!'}), 403
    engineers = get_engineers()
    # Attach current open ticket count for each engineer
    from ..models import execute_query
    result = []
    for eng in engineers:
        row = execute_query(
            "SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Open','In Progress')",
            (eng['id'],), fetchone=True
        )
        result.append({
            'id': eng['id'],
            'name': eng['full_name'],
            'email': eng['email'],
            'assigned': row['c'] if row else 0
        })
    return jsonify({'success': True, 'engineers': result})
