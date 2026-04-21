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


def _effective_deadline_sql(alias='t'):
    return (
        f"LEAST({alias}.sla_deadline, {alias}.created_at + "
        f"(CASE {alias}.priority "
        f"WHEN 'Critical' THEN interval '2 hours' "
        f"WHEN 'High' THEN interval '8 hours' "
        f"WHEN 'Medium' THEN interval '20 hours' "
        f"ELSE interval '50 hours' END))"
    )

def get_db():
    try:
        url = Config.POSTGRES_URL
        if not url:
            _debug_log('DB_ERR', 'models.py:get_db', 'POSTGRES_URL is None', {})
            return None
        conn = psycopg2.connect(url)
        return conn
    except Exception as e:
        _debug_log('DB_ERR', 'models.py:get_db', f'Connection failed: {str(e)}', {'url_present': bool(Config.POSTGRES_URL)})
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
    effective_deadline = _effective_deadline_sql('t')
    query = """
        SELECT
            t.*,
            u1.full_name as creator_name,
            u1.email as creator_email,
            u2.full_name as assignee_name,
            u2.email as assignee_email,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline}
                ELSE {effective_deadline} < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
    """.format(effective_deadline=effective_deadline)
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
    effective_deadline = _effective_deadline_sql('t')
    ticket = execute_query(
        """
        SELECT
            t.*,
            u1.full_name as creator_name,
            u2.full_name as assignee_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline}
                ELSE {effective_deadline} < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE t.id = %s
        """.format(effective_deadline=effective_deadline),
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
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    engineer = execute_query("SELECT full_name, role FROM users WHERE id = %s", (engineer_id,), fetchone=True)
    if not engineer or engineer['role'].lower() != 'engineer':
        return False

    ticket = execute_query("SELECT id FROM tickets WHERE id = %s", (ticket_id,), fetchone=True)
    if not ticket:
        return False
        
    execute_query(
        "UPDATE tickets SET assigned_to = %s, status = 'In Progress', updated_at = %s WHERE id = %s",
        (engineer_id, now, ticket_id),
        commit=True
    )
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
    effective_deadline = _effective_deadline_sql('t')
    active = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    resolved = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND status IN ('Resolved', 'Closed')", (user_id,), fetchone=True)['count']
    total = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s", (user_id,), fetchone=True)['count']
    urgent = execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND priority IN ('Critical', 'High') AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    breached = execute_query(
        f"SELECT COUNT(*) as count FROM tickets t WHERE created_by = %s AND ((status IN ('Open', 'In Progress') AND {effective_deadline} < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > {effective_deadline}))",
        (user_id, now),
        fetchone=True
    )['count']
    breached_resolved = execute_query(
        f"SELECT COUNT(*) as count FROM tickets t WHERE created_by = %s AND status IN ('Resolved', 'Closed') AND updated_at > {effective_deadline}",
        (user_id,),
        fetchone=True
    )['count']
    sla_met = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE created_by = %s AND status IN ('Resolved', 'Closed') AND updated_at <= {effective_deadline}", (user_id,), fetchone=True)['count']
    breached_lifetime = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE created_by = %s AND {effective_deadline} < %s::timestamp", (user_id, now), fetchone=True)['count']
    
    # Calculate MTTR for member
    mttr_row = execute_query(
        f"SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE created_by = %s AND status IN ('Resolved', 'Closed')",
        (user_id,), fetchone=True
    )
    mttr = round(float(mttr_row['mttr']), 1) if mttr_row and mttr_row['mttr'] is not None else 0.0
    
    sla_pct = round((sla_met / resolved * 100), 1) if resolved > 0 else 0
    priority_counts = {p: execute_query("SELECT COUNT(*) as count FROM tickets WHERE created_by = %s AND priority = %s", (user_id, p), fetchone=True)['count'] for p in ['Critical', 'High', 'Medium', 'Low']}
    tickets = execute_query(
        """
        SELECT
            t.*,
            u.full_name as assignee_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline}
                ELSE {effective_deadline} < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.created_by = %s
        ORDER BY t.created_at DESC
        """.format(effective_deadline=effective_deadline),
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
    return {
        'active': active,
        'resolved': resolved,
        'total': total,
        'urgent': urgent,
        'breached': breached,
        'breached_resolved': breached_resolved,
        'sla_met': sla_met,
        'sla_pct': sla_pct,
        'mttr': f"{mttr}h",
        'priorityData': list(priority_counts.values()),
        'tickets': [dict(t) for t in (tickets or [])]
    }

def get_engineer_stats(user_id):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    effective_deadline = _effective_deadline_sql('t')
    assigned = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Open', 'In Progress')", (user_id,), fetchone=True)['count']
    overdue = execute_query(
        f"SELECT COUNT(*) as count FROM tickets t WHERE assigned_to = %s AND ((status IN ('Open', 'In Progress') AND {effective_deadline} < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > {effective_deadline}))",
        (user_id, now),
        fetchone=True
    )['count']
    resolved_total = execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed')", (user_id,), fetchone=True)['count']
    sla_met = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE assigned_to = %s AND status IN ('Resolved', 'Closed') AND updated_at <= {effective_deadline}", (user_id,), fetchone=True)['count']
    breached_lifetime = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE assigned_to = %s AND {effective_deadline} < %s::timestamp", (user_id, now), fetchone=True)['count']
    
    # MTTR for engineer
    mttr_row = execute_query(
        f"SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed')",
        (user_id,), fetchone=True
    )
    mttr = round(float(mttr_row['mttr']), 1) if mttr_row and mttr_row['mttr'] is not None else 0.0

    # Resolved within last 5 tickets for trend
    resolved_trend_rows = execute_query(
        "SELECT EXTRACT(EPOCH FROM (updated_at - created_at))/3600 as val FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed') ORDER BY updated_at DESC LIMIT 5",
        (user_id,)
    )
    mttr_trend = [round(float(r['val']), 1) for r in (resolved_trend_rows or [])][::-1]
    while len(mttr_trend) < 5: mttr_trend.insert(0, 0)

    sla_pct = round((sla_met / resolved_total * 100), 1) if resolved_total > 0 else 0
    queue = execute_query(
        """
        SELECT
            t.*,
            u.full_name as creator_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline}
                ELSE {effective_deadline} < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.assigned_to = %s AND t.status IN ('Open', 'In Progress')
        ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, t.created_at ASC
        """.format(effective_deadline=effective_deadline),
        (user_id,)
    )
    resolved_list = execute_query(
        """
        SELECT
            t.*,
            u.full_name as creator_name,
            CASE
                WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline}
                ELSE {effective_deadline} < CURRENT_TIMESTAMP
            END as sla_breached
        FROM tickets t
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.assigned_to = %s AND t.status IN ('Resolved', 'Closed')
        ORDER BY t.updated_at DESC
        LIMIT 10
        """.format(effective_deadline=effective_deadline),
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
    return {'assigned': assigned, 'overdue': overdue, 'resolved_total': resolved_total, 'sla_pct': sla_pct, 'mttr': f"{mttr}h", 'mttr_trend': mttr_trend, 'queue': [dict(t) for t in (queue or [])], 'resolved_list': [dict(t) for t in (resolved_list or [])]}

def get_admin_stats():
    # Defensive Default Values
    defaults = {
        'total_open': 0, 'breaches_today': 0, 'escalated': 0, 'total_resolved': 0, 'total_all': 0,
        'reopen_rate': 0.0, 'mttr': '0.0h', 'avg_aging': '0.0d',
        'slaComplianceData': [0, 0, 0], 'agingData': [0, 0, 0, 0],
        'backlogTrendData': [0, 0, 0, 0, 0, 0, 0],
        'serviceImpactData': [0, 0, 0, 0, 0],
        'regionLoadData': [0, 0, 0, 0],
        'engineers': [], 'all_tickets': []
    }

    try:
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        effective_deadline = _effective_deadline_sql('t')
        
        # ── KPI METRICS ──────────────────────────────────────────────────────
        total_open = (execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress')", fetchone=True) or {'count': 0})['count']
        open_breached = (execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open', 'In Progress') AND {effective_deadline} < %s::timestamp", (now,), fetchone=True) or {'count': 0})['count']
        resolved_breached = (execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Resolved', 'Closed') AND updated_at > {effective_deadline}", fetchone=True) or {'count': 0})['count']
        breaches_today = open_breached + resolved_breached
        escalated = (execute_query("SELECT COUNT(*) as count FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'In Progress')", fetchone=True) or {'count': 0})['count']
        total_resolved = (execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True) or {'count': 0})['count']
        total_all = (execute_query("SELECT COUNT(*) as count FROM tickets", fetchone=True) or {'count': 0})['count']
        
        near_breach = (execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open', 'In Progress') AND {effective_deadline} > %s::timestamp AND {effective_deadline} < %s::timestamp + interval '2 hours'", (now, now), fetchone=True) or {'count': 0})['count']
        compliant = max(0, total_all - near_breach - breaches_today)
        
        mttr_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)
        mttr = round(float(mttr_row['mttr']), 1) if mttr_row and mttr_row.get('mttr') is not None else 0.0
        
        aging_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/86400) as aging FROM tickets WHERE status IN ('Open', 'In Progress')", fetchone=True)
        avg_aging = round(float(aging_row['aging']), 1) if aging_row and aging_row.get('aging') is not None else 0.0

        # ── TRENDS & DISTRIBUTIONS ───────────────────────────────────────────
        trend_rows = execute_query("""
            SELECT d.day, COUNT(t.id) as count
            FROM (SELECT CURRENT_DATE - i as day FROM generate_series(0,6) i) d
            LEFT JOIN tickets t ON DATE(t.created_at) = d.day
            GROUP BY d.day ORDER BY d.day ASC
        """)
        backlog_trend = [int(r['count']) for r in (trend_rows or [])]

        reopens = (execute_query("SELECT COUNT(*) as count FROM audit_logs WHERE action LIKE 'Status → In Progress' AND details LIKE '%status changed to In Progress%'", fetchone=True) or {'count': 0})['count']
        reopen_rate = round((reopens / total_all * 100), 1) if total_all > 0 else 0.0
        
        aging = [ (execute_query(f"SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress') AND {q}", fetchone=True) or {'count': 0})['count'] for q in [
            "created_at >= CURRENT_TIMESTAMP - interval '1 day'", 
            "created_at < CURRENT_TIMESTAMP - interval '1 day' AND created_at >= CURRENT_TIMESTAMP - interval '3 days'", 
            "created_at < CURRENT_TIMESTAMP - interval '3 days' AND created_at >= CURRENT_TIMESTAMP - interval '7 days'", 
            "created_at < CURRENT_TIMESTAMP - interval '7 days'"
        ]]
        
        services = ['Database', 'Networking', 'Compute / VM', 'Security / IAM', 'Storage']
        service_counts = [(execute_query("SELECT COUNT(*) as count FROM tickets WHERE service_area = %s AND status IN ('Open', 'In Progress')", (svc,), fetchone=True) or {'count': 0})['count'] for svc in services]
        
        envs = ['Production', 'Staging', 'Development', 'Local']
        region_counts = [(execute_query("SELECT COUNT(*) as count FROM tickets WHERE environment = %s AND status IN ('Open', 'In Progress')", (env,), fetchone=True) or {'count': 0})['count'] for env in envs]

        # ── ENGINEER PERFORMANCE ─────────────────────────────────────────────
        engineers = execute_query("SELECT id, full_name, email FROM users WHERE role = 'engineer'")
        engineer_data = []
        for eng in (engineers or []):
            try:
                ea = (execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Open', 'In Progress')", (eng['id'],), fetchone=True) or {'count': 0})['count']
                er = (execute_query("SELECT COUNT(*) as count FROM tickets WHERE assigned_to = %s AND status IN ('Resolved', 'Closed')", (eng['id'],), fetchone=True) or {'count': 0})['count']
                esm = (execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE assigned_to = %s AND status IN ('Resolved', 'Closed') AND updated_at <= {effective_deadline}", (eng['id'],), fetchone=True) or {'count': 0})['count']
                esp = round((esm / er * 100)) if er > 0 else 0
                eb = (execute_query(
                    f"SELECT COUNT(*) as count FROM tickets t WHERE assigned_to = %s AND ((status IN ('Open', 'In Progress') AND {effective_deadline} < %s::timestamp) OR (status IN ('Resolved', 'Closed') AND updated_at > {effective_deadline}))",
                    (eng['id'], now),
                    fetchone=True
                ) or {'count': 0})['count']
                engineer_data.append({
                    'id': eng['id'], 'name': eng['full_name'], 'assigned': ea, 'resolved': er, 'mttr': '-', 'sla': esp, 
                    'reopens': '0%', 'status': 'excellent' if esp >= 95 else 'good' if esp >= 85 else 'warning' if esp >= 70 else 'critical', 'breached': eb
                })
            except Exception:
                continue

        # ── TICKETS LIST ─────────────────────────────────────────────────────
        all_tickets = execute_query(
            f"""
            SELECT t.*, u1.full_name as creator_name, u2.full_name as assignee_name,
            CASE WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {effective_deadline} ELSE {effective_deadline} < CURRENT_TIMESTAMP END as sla_breached
            FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id
            ORDER BY t.created_at DESC
            """
        )

        return {
            'total_open': total_open, 'breaches_today': breaches_today, 'escalated': escalated,
            'total_resolved': total_resolved, 'total_all': total_all, 'reopen_rate': reopen_rate,
            'mttr': f"{mttr}h", 'avg_aging': f"{avg_aging}d",
            'slaComplianceData': [compliant, near_breach, breaches_today],
            'agingData': aging, 'backlogTrendData': backlog_trend, 'serviceImpactData': service_counts, 'regionLoadData': region_counts,
            'engineers': engineer_data, 'all_tickets': [dict(t) for t in (all_tickets or [])]
        }
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        _debug_log('ADMIN_STATS_ERR', 'models.py:get_admin_stats', f'Aggregation failed: {str(e)}', {'traceback': err_msg})
        print(f"CRITICAL ERROR in get_admin_stats: {e}")
        return defaults
