"""
Database models and helpers for InfraTick.
Uses PostgreSQL via psycopg2 for persistence.
"""

import psycopg2
import psycopg2.extras
import os
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config

# SLA deadlines in hours by priority
SLA_HOURS = {
    'Critical': 2,
    'High': 8,
    'Medium': 20,
    'Low': 50
}


def _debug_log(hypothesis_id, location, message, data, run_id='initial'):
    try:
        log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'debug-c9a78c.log'))
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'sessionId': 'c9a78c',
                'runId': run_id,
                'hypothesisId': hypothesis_id,
                'location': location,
                'message': message,
                'data': data,
                'timestamp': int(datetime.utcnow().timestamp() * 1000)
            }) + '\n')
    except Exception:
        pass

def get_db():
    try:
        conn = psycopg2.connect(Config.POSTGRES_URL)
        return conn
    except Exception as e:
        print("Database connection error:", e)
        return None

def init_db():
    conn = get_db()
    if not conn: return
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('member', 'engineer', 'admin')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            service_area TEXT NOT NULL DEFAULT 'Other',
            environment TEXT NOT NULL DEFAULT 'Production',
            priority TEXT NOT NULL CHECK(priority IN ('Critical', 'High', 'Medium', 'Low')),
            status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
            sla_deadline TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER NOT NULL REFERENCES users(id),
            assigned_to INTEGER REFERENCES users(id)
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            icon TEXT NOT NULL DEFAULT 'fa-info-circle',
            color TEXT NOT NULL DEFAULT '#3b82f6',
            danger INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER REFERENCES users(id),
            ticket_id INTEGER REFERENCES tickets(id),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Seed admin account if not exists
    cursor.execute("SELECT id FROM users WHERE email = %s", ('manik102@gmail.com',))
    existing = cursor.fetchone()

    if not existing:
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
            ('Manik', 'manik102@gmail.com', generate_password_hash('123456'), 'admin')
        )
        admin_id = cursor.fetchone()[0]
        
        cursor.execute(
            "INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (%s, %s, %s, %s, %s)",
            ('System Initialized', 'Admin account created for Manik', 'fa-shield-alt', '#10b981', admin_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

def _serialize_row(row):
    """Convert datetime objects in a RealDictRow to ISO format strings."""
    if row is None:
        return None
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.strftime('%Y-%m-%d %H:%M:%S')
    return result

def execute_query(query, params=(), commit=False, fetchone=False):
    conn = get_db()
    if not conn: return None
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
        if cursor.description:
            if fetchone:
                row = cursor.fetchone()
                return _serialize_row(row)
            rows = cursor.fetchall()
            return [_serialize_row(r) for r in rows]
        return None
    finally:
        cursor.close()
        conn.close()


def create_user(full_name, email, password, role):
    try:
        user = execute_query("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING *",
                     (full_name, email, generate_password_hash(password), role.lower()), commit=True, fetchone=True)
        execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (%s, %s, %s, %s, %s)",
                     ('User Registered', f'{full_name} registered as {role}', 'fa-user-plus', '#3b82f6', user['id']), commit=True)
        return dict(user)
    except psycopg2.IntegrityError:
        return None

def get_user_by_email(email):
    user = execute_query("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)
    return dict(user) if user else None

def get_user_by_id(user_id):
    user = execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetchone=True)
    return dict(user) if user else None

def get_all_users():
    users = execute_query("SELECT id, full_name, email, role, created_at FROM users")
    return [dict(u) for u in (users or [])]

def get_engineers():
    engineers = execute_query("SELECT id, full_name, email, role, created_at FROM users WHERE role = 'engineer'")
    return [dict(e) for e in (engineers or [])]

def create_ticket(subject, description, service_area, environment, priority, created_by):
    sla_hours = SLA_HOURS.get(priority, 50)
    now = datetime.utcnow()
    sla_deadline = (now + timedelta(hours=sla_hours)).strftime('%Y-%m-%d %H:%M:%S')
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    ticket = execute_query("INSERT INTO tickets (subject, description, service_area, environment, priority, status, sla_deadline, created_at, updated_at, created_by) VALUES (%s, %s, %s, %s, %s, 'Open', %s, %s, %s, %s) RETURNING *",
                   (subject, description, service_area, environment, priority, sla_deadline, now_str, now_str, created_by), commit=True, fetchone=True)
    
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)",
                   ('Ticket Created', f'#{ticket["id"]} — {subject} [{priority}]', 'fa-ticket-alt', '#3b82f6', created_by, ticket["id"]), commit=True)
    return dict(ticket)

def get_tickets(filters=None):
    query = """
        SELECT
            t.*,
            u1.full_name as creator_name,
            u1.email as creator_email,
            u2.full_name as assignee_name,
            u2.email as assignee_email,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
    """
    conditions = []
    params = []
    if filters:
        for k, v in filters.items():
            conditions.append(f"t.{k} = %s")
            params.append(v)
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY t.created_at DESC"
    tickets = execute_query(query, tuple(params))
    return [dict(t) for t in (tickets or [])]

def get_ticket_by_id(ticket_id):
    ticket = execute_query(
        """
        SELECT
            t.*,
            u1.full_name as creator_name,
            u2.full_name as assignee_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE t.id = %s
        """,
        (ticket_id,),
        fetchone=True
    )
    return dict(ticket) if ticket else None

def update_ticket_status(ticket_id, new_status, user_id):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query("UPDATE tickets SET status = %s, updated_at = %s WHERE id = %s", (new_status, now, ticket_id), commit=True)
    icon_map = {'In Progress': ('fa-spinner', '#3b82f6'), 'Resolved': ('fa-check-circle', '#10b981'), 'Closed': ('fa-times-circle', '#64748b'), 'Open': ('fa-folder-open', '#f59e0b')}
    icon, color = icon_map.get(new_status, ('fa-edit', '#3b82f6'))
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)", (f'Status → {new_status}', f'Ticket #{ticket_id} status changed to {new_status}', icon, color, user_id, ticket_id), commit=True)

def assign_ticket(ticket_id, engineer_id, admin_id):
    now_dt = datetime.utcnow()
    now = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    engineer = execute_query("SELECT full_name, role FROM users WHERE id = %s", (engineer_id,), fetchone=True)
    if not engineer or engineer['role'].lower() != 'engineer':
        return False

    ticket = execute_query("SELECT priority FROM tickets WHERE id = %s", (ticket_id,), fetchone=True)
    if not ticket:
        return False
        
    priority = ticket['priority']
    sla_hours = SLA_HOURS.get(priority, 50)
    new_sla_deadline = (now_dt + timedelta(hours=sla_hours)).strftime('%Y-%m-%d %H:%M:%S')

    execute_query("UPDATE tickets SET assigned_to = %s, status = 'In Progress', updated_at = %s, sla_deadline = %s WHERE id = %s", (engineer_id, now, new_sla_deadline, ticket_id), commit=True)
    engineer_name = engineer['full_name']
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)", ('Ticket Assigned', f'Ticket #{ticket_id} assigned to {engineer_name}', 'fa-user-cog', '#8b5cf6', admin_id, ticket_id), commit=True)
    return True

def add_comment(ticket_id, user_id, text):
    execute_query("INSERT INTO comments (ticket_id, user_id, text) VALUES (%s, %s, %s)", (ticket_id, user_id, text), commit=True)

def get_comments(ticket_id):
    comments = execute_query("SELECT c.*, u.full_name as user_name, u.role as user_role FROM comments c JOIN users u ON c.user_id = u.id WHERE c.ticket_id = %s ORDER BY c.created_at ASC", (ticket_id,))
    return [dict(c) for c in (comments or [])]

def get_audit_logs(limit=20):
    logs = execute_query("SELECT a.*, u.full_name as user_name FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id ORDER BY a.created_at DESC LIMIT %s", (limit,))
    return [dict(l) for l in (logs or [])]

def add_audit_log(action, details, icon='fa-info-circle', color='#3b82f6', danger=False, user_id=None, ticket_id=None):
    execute_query("INSERT INTO audit_logs (action, details, icon, color, danger, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (action, details, icon, color, 1 if danger else 0, user_id, ticket_id), commit=True)

def get_member_stats(user_id):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    active = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    resolved = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND status IN ('Resolved', 'Closed')", (user_id,), fetchone=True)['count']
    total = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s", (user_id,), fetchone=True)['count']
    urgent = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND priority IN ('Critical', 'High') AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    breached = execute_query(
        "SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND ((status IN ('Open', 'In Progress') AND sla_deadline < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > sla_deadline))",
        (user_id, now),
        fetchone=True
    )['count']
    sla_met = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (user_id,), fetchone=True)['count']
    breached_lifetime = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND sla_deadline < %s::timestamp", (user_id, now), fetchone=True)['count']
    sla_pct = round((sla_met / resolved * 100), 1) if resolved > 0 else 0
    priority_counts = {p: execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND priority = %s", (user_id, p), fetchone=True)['count'] for p in ['Critical', 'High', 'Medium', 'Low']}
    tickets = execute_query(
        """
        SELECT
            t.*,
            u.full_name as assignee_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.created_by = %s
        ORDER BY t.created_at DESC
        """,
        (user_id,)
    )
    # #region agent log
    _debug_log('H1', 'backend/app/models.py:get_member_stats', 'member breach counters', {
        'userId': user_id,
        'active': active,
        'resolved': resolved,
        'breachedOpenOnly': breached,
        'breachedLifetime': breached_lifetime
    })
    # #endregion
    return {'active': active, 'resolved': resolved, 'total': total, 'urgent': urgent, 'breached': breached, 'sla_pct': sla_pct, 'priorityData': list(priority_counts.values()), 'tickets': [dict(t) for t in (tickets or [])]}

def get_engineer_stats(user_id):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    assigned = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    overdue = execute_query(
        "SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND ((status IN ('Open', 'In Progress') AND sla_deadline < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > sla_deadline))",
        (user_id, now),
        fetchone=True
    )['count']
    resolved_total = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed')", (user_id,), fetchone=True)['count']
    sla_met = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (user_id,), fetchone=True)['count']
    breached_lifetime = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND sla_deadline < %s::timestamp", (user_id, now), fetchone=True)['count']
    sla_pct = round((sla_met / resolved_total * 100), 1) if resolved_total > 0 else 0
    queue = execute_query(
        """
        SELECT
            t.*,
            u.full_name as creator_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.assigned_to = %s AND t.status IN ('Open', 'In Progress')
        ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, t.created_at ASC
        """,
        (user_id,)
    )
    resolved_list = execute_query(
        """
        SELECT
            t.*,
            u.full_name as creator_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.assigned_to = %s AND t.status IN ('Resolved', 'Closed')
        ORDER BY t.updated_at DESC
        LIMIT 10
        """,
        (user_id,)
    )
    # #region agent log
    _debug_log('H2', 'backend/app/models.py:get_engineer_stats', 'engineer breach counters', {
        'userId': user_id,
        'assignedOpen': assigned,
        'resolvedTotal': resolved_total,
        'overdueOpenOnly': overdue,
        'breachedLifetime': breached_lifetime
    })
    # #endregion
    return {'assigned': assigned, 'overdue': overdue, 'resolved_total': resolved_total, 'sla_pct': sla_pct, 'queue': [dict(t) for t in (queue or [])], 'resolved_list': [dict(t) for t in (resolved_list or [])]}

def get_admin_stats():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    total_open = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress')", fetchone=True)['count']
    open_breached = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress') AND sla_deadline < %s::timestamp", (now,), fetchone=True)['count']
    resolved_breached = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed') AND updated_at > sla_deadline", fetchone=True)['count']
    breaches_today = open_breached + resolved_breached
    escalated = execute_query("SELECT COUNT(*) as count FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'In Progress')", fetchone=True)['count']
    total_resolved = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)['count']
    total_all = execute_query("SELECT COUNT(*) as count FROM tickets", fetchone=True)['count']
    sla_met = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", fetchone=True)['count']
    breached_total_lifetime = execute_query("SELECT COUNT(*) as count FROM tickets WHERE sla_deadline < %s::timestamp", (now,), fetchone=True)['count']
    breached_resolved = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed') AND updated_at > sla_deadline", fetchone=True)['count']
    near_breach = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress') AND sla_deadline > %s::timestamp AND sla_deadline < %s::timestamp + interval '2 hours'", (now, now), fetchone=True)['count']
    compliant = max(0, total_all - near_breach - breaches_today)
    aging = [execute_query(f"SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress') AND {q}", fetchone=True)['count'] for q in ["created_at >= CURRENT_TIMESTAMP - interval '1 day'", "created_at < CURRENT_TIMESTAMP - interval '1 day' AND created_at >= CURRENT_TIMESTAMP - interval '3 days'", "created_at < CURRENT_TIMESTAMP - interval '3 days' AND created_at >= CURRENT_TIMESTAMP - interval '7 days'", "created_at < CURRENT_TIMESTAMP - interval '7 days'"]]
    services = ['Database', 'Networking', 'Compute / VM', 'Security / IAM', 'Storage']
    service_counts = [execute_query("SELECT COUNT(*) as count FROM tickets WHERE service_area = %s AND status IN ('Open', 'In Progress')", (svc,), fetchone=True)['count'] for svc in services]
    engineers = execute_query("SELECT id, full_name, email FROM users WHERE role = 'engineer'")
    engineer_data = []
    for eng in (engineers or []):
        ea = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Open', 'In Progress')", (eng['id'],), fetchone=True)['count']
        er = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed')", (eng['id'],), fetchone=True)['count']
        esm = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (eng['id'],), fetchone=True)['count']
        esp = round((esm / er * 100)) if er > 0 else 0
        eb = execute_query(
            "SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND ((status IN ('Open', 'In Progress') AND sla_deadline < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > sla_deadline))",
            (eng['id'], now),
            fetchone=True
        )['count']
        engineer_data.append({'id': eng['id'], 'name': eng['full_name'], 'assigned': ea, 'resolved': er, 'mttr': '-', 'sla': esp, 'reopens': '0%', 'status': 'excellent' if esp >= 95 else 'good' if esp >= 85 else 'warning' if esp >= 70 else 'critical', 'breached': eb})
    all_tickets = execute_query(
        """
        SELECT
            t.*,
            u1.full_name as creator_name,
            u2.full_name as assignee_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > t.sla_deadline
                ELSE t.sla_deadline < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        ORDER BY t.created_at DESC
        """
    )
    # #region agent log
    _debug_log('H3', 'backend/app/models.py:get_admin_stats', 'admin sla aggregate counters', {
        'totalOpen': total_open,
        'totalResolved': total_resolved,
        'breachesOpenOnly': open_breached,
        'breachedResolved': breached_resolved,
        'breachedLifetime': breached_total_lifetime,
        'slaComplianceData': [compliant, near_breach, breaches_today]
    })
    # #endregion
    # #region agent log
    _debug_log('H4', 'backend/app/models.py:get_admin_stats', 'engineer matrix preview', {
        'engineerCount': len(engineer_data),
        'engineerRows': [{
            'id': e['id'],
            'resolved': e['resolved'],
            'sla': e['sla'],
            'status': e['status']
        } for e in engineer_data]
    })
    # #endregion
    return {'total_open': total_open, 'breaches_today': breaches_today, 'escalated': escalated, 'total_resolved': total_resolved, 'total_all': total_all, 'reopen_rate': 0, 'slaComplianceData': [compliant, near_breach, breaches_today], 'agingData': aging, 'backlogTrendData': [total_open, 0,0,0,0,0], 'serviceImpactData': service_counts, 'regionLoadData': [total_open, 0,0,0], 'engineers': engineer_data, 'all_tickets': [dict(t) for t in (all_tickets or [])]}
