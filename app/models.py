"""
Database models and helpers for InfraTick.
Uses PostgreSQL via pg8000 (Pure Python) for persistence.
"""

# pg8000 is lazily imported inside get_db() to prevent Vercel cold-start crashes
import os
import json
from datetime import datetime, timedelta, date
from urllib.parse import urlparse
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
    """Safe logger that avoids crashing on Read-Only file systems like Vercel."""
    log_entry = {
        'sessionId': 'c9a78c',
        'runId': run_id,
        'hypothesisId': hypothesis_id,
        'location': location,
        'message': message,
        'data': data
    }
    print(f"[DEBUG][{hypothesis_id}] {message}")
    
    if not os.environ.get('VERCEL'):
        try:
            log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'debug-c9a78c.log'))
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
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
    """Returns a DB-API 2.0 compatible connection using pg8000 (Pure Python)."""
    try:
        import pg8000.dbapi  # Lazy import - prevents Vercel cold-start crash
        pg_url = Config.POSTGRES_URL
        if pg_url:
            result = urlparse(pg_url)
            conn = pg8000.dbapi.connect(
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port or 5432,
                database=result.path[1:],
                ssl_context=True
            )
            return conn
        return None
    except Exception as e:
        _debug_log('DB_CONN_ERR', 'models.py:get_db', str(e), {})
        return None

def init_db():
    conn = get_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN (\'member\', \'engineer\', \'admin\')), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);')
        cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id SERIAL PRIMARY KEY, subject TEXT NOT NULL, description TEXT NOT NULL DEFAULT \'\', service_area TEXT NOT NULL DEFAULT \'Other\', environment TEXT NOT NULL DEFAULT \'Production\', priority TEXT NOT NULL CHECK(priority IN (\'Critical\', \'High\', \'Medium\', \'Low\')), status TEXT NOT NULL DEFAULT \'Open\' CHECK(status IN (\'Open\', \'In Progress\', \'Resolved\', \'Closed\')), sla_deadline TIMESTAMP NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, created_by INTEGER NOT NULL REFERENCES users(id), assigned_to INTEGER REFERENCES users(id));')
        cursor.execute('CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);')
        cursor.execute('CREATE TABLE IF NOT EXISTS audit_logs (id SERIAL PRIMARY KEY, action TEXT NOT NULL, details TEXT NOT NULL DEFAULT \'\', icon TEXT NOT NULL DEFAULT \'fa-info-circle\', color TEXT NOT NULL DEFAULT \'#3b82f6\', danger INTEGER NOT NULL DEFAULT 0, user_id INTEGER REFERENCES users(id), ticket_id INTEGER REFERENCES tickets(id), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);')
        
        cursor.execute("SELECT id FROM users WHERE email = %s", ('manik102@gmail.com',))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
                         ('Manik', 'manik102@gmail.com', generate_password_hash('123456'), 'admin'))
            admin_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (%s, %s, %s, %s, %s)",
                         ('System Initialized', 'Admin account created for Manik', 'fa-shield-alt', '#10b981', admin_id))
        conn.commit()
    finally:
        conn.close()

def _serialize_row(row, columns):
    if row is None: return None
    result = dict(zip(columns, row))
    for key, value in result.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.strftime('%Y-%m-%d %H:%M:%S')
    return result

def execute_query(query, params=(), commit=False, fetchone=False):
    conn = get_db()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        if commit: conn.commit()
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            if fetchone:
                return _serialize_row(cursor.fetchone(), columns)
            return [_serialize_row(r, columns) for r in cursor.fetchall()]
        return None
    except Exception as e:
        _debug_log('SQL_ERR', 'models.py', str(e), {'query': query})
        return None
    finally:
        if conn: conn.close()

def create_user(full_name, email, password, role):
    user = execute_query("INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING *",
                 (full_name, email, generate_password_hash(password), role.lower()), commit=True, fetchone=True)
    if user:
        execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (%s, %s, %s, %s, %s)",
                     ('User Registered', f'{full_name} registered as {role}', 'fa-user-plus', '#3b82f6', user['id']), commit=True)
    return user

def get_user_by_email(email):
    return execute_query("SELECT * FROM users WHERE email = %s", (email,), fetchone=True)

def get_user_by_id(user_id):
    return execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetchone=True)

def get_all_users():
    return execute_query("SELECT id, full_name, email, role, created_at FROM users") or []

def get_engineers():
    return execute_query("SELECT id, full_name, email, role, created_at FROM users WHERE role = 'engineer'") or []

def create_ticket(subject, description, service_area, environment, priority, created_by):
    sla_hours = SLA_HOURS.get(priority, 50)
    now = datetime.utcnow()
    sla_deadline = (now + timedelta(hours=sla_hours)).strftime('%Y-%m-%d %H:%M:%S')
    ticket = execute_query("INSERT INTO tickets (subject, description, service_area, environment, priority, status, sla_deadline, created_at, updated_at, created_by) VALUES (%s, %s, %s, %s, %s, 'Open', %s, %s, %s, %s) RETURNING *",
                   (subject, description, service_area, environment, priority, sla_deadline, now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S'), created_by), commit=True, fetchone=True)
    if ticket:
        execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)",
                       ('Ticket Created', f'#{ticket["id"]} — {subject} [{priority}]', 'fa-ticket-alt', '#3b82f6', created_by, ticket["id"]), commit=True)
    return ticket

def get_tickets(filters=None):
    dead = _effective_deadline_sql('t')
    query = f"SELECT t.*, u1.full_name as creator_name, u2.full_name as assignee_name, CASE WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {dead} ELSE {dead} < CURRENT_TIMESTAMP END as sla_breached FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id"
    params = []
    if filters:
        conds = [f"t.{k} = %s" for k in filters]
        query += " WHERE " + " AND ".join(conds)
        params = list(filters.values())
    query += " ORDER BY t.created_at DESC"
    return execute_query(query, tuple(params)) or []

def get_ticket_by_id(ticket_id):
    dead = _effective_deadline_sql('t')
    return execute_query(f"SELECT t.*, u1.full_name as creator_name, u2.full_name as assignee_name, CASE WHEN t.status IN ('Resolved', 'Closed') THEN t.updated_at > {dead} ELSE {dead} < CURRENT_TIMESTAMP END as sla_breached FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id WHERE t.id = %s", (ticket_id,), fetchone=True)

def update_ticket_status(ticket_id, new_status, user_id):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query("UPDATE tickets SET status = %s, updated_at = %s WHERE id = %s", (new_status, now, ticket_id), commit=True)
    im = {'In Progress': ('fa-spinner', '#3b82f6'), 'Resolved': ('fa-check-circle', '#10b981'), 'Closed': ('fa-times-circle', '#64748b')}
    icon, col = im.get(new_status, ('fa-edit', '#3b82f6'))
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)", (f'Status → {new_status}', f'Ticket #{ticket_id} status changed to {new_status}', icon, col, user_id, ticket_id), commit=True)

def assign_ticket(tid, eid, aid):
    eng = execute_query("SELECT full_name FROM users WHERE id = %s AND role = 'engineer'", (eid,), fetchone=True)
    if not eng: return False
    execute_query("UPDATE tickets SET assigned_to = %s, status = 'In Progress', updated_at = %s WHERE id = %s", (eid, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), tid), commit=True)
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)", ('Ticket Assigned', f'Ticket #{tid} assigned to {eng["full_name"]}', 'fa-user-cog', '#8b5cf6', aid, tid), commit=True)
    return True

def get_admin_stats():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = { 'total_open': 0, 'breaches_today': 0, 'escalated': 0, 'total_resolved': 0, 'total_all': 0, 'mttr': '0.0h', 'avg_aging': '0.0d', 'slaComplianceData': [0,0,0], 'serviceImpactData': [0,0,0,0,0], 'regionLoadData': [0,0,0,0], 'engineers': [], 'all_tickets': [] }
    try:
        res['total_open'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress')", fetchone=True)['count']
        res['total_all'] = execute_query("SELECT COUNT(*) as count FROM tickets", fetchone=True)['count']
        res['total_resolved'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)['count']
        b1 = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open', 'In Progress') AND {dead} < %s::timestamp", (now,), fetchone=True)['count']
        b2 = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Resolved', 'Closed') AND updated_at > {dead}", fetchone=True)['count']
        res['breaches_today'] = b1 + b2
        res['escalated'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'In Progress')", fetchone=True)['count']
        
        m_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)
        res['mttr'] = f"{round(float(m_row['mttr'] or 0), 1)}h"
        
        svc_map = {'Database':0, 'Networking':1, 'Compute / VM':2, 'Security / IAM':3, 'Storage':4}
        svcs = execute_query("SELECT service_area, COUNT(*) as c FROM tickets GROUP BY service_area")
        for s in (svcs or []):
            if s['service_area'] in svc_map: res['serviceImpactData'][svc_map[s['service_area']]] = s['c']
            
        env_map = {'Production':0, 'Staging':1, 'Development':2, 'Local':3}
        envs = execute_query("SELECT environment, COUNT(*) as c FROM tickets GROUP BY environment")
        for e in (envs or []):
            if e['environment'] in env_map: res['regionLoadData'][env_map[e['environment']]] = e['c']
            
        res['all_tickets'] = get_tickets()
    except Exception as e: _debug_log('ADMIN_ERR', 'models.py', str(e), {})
    return res

def get_member_stats(uid):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = {'active':0, 'resolved':0, 'total':0, 'urgent':0, 'breached':0, 'sla_pct':0, 'mttr':'0h', 'priorityData':[0,0,0,0], 'tickets':[]}
    try:
        res['active'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['resolved'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True)['c']
        res['total'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s", (uid,), fetchone=True)['c']
        res['urgent'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND priority='Critical' AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['breached'] = execute_query(f"SELECT COUNT(*) as c FROM tickets t WHERE created_by=%s AND (({dead} < %s::timestamp AND status IN ('Open','In Progress')) OR (updated_at > {dead} AND status IN ('Resolved','Closed')))", (uid, now), fetchone=True)['c']
        res['tickets'] = get_tickets({'created_by': uid})
    except Exception as e: _debug_log('MEM_ERR', 'models.py', str(e), {})
    return res

def get_engineer_stats(uid):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = {'assigned':0, 'overdue':0, 'resolved_total':0, 'sla_pct':0, 'mttr':'0h', 'queue':[], 'resolved_list':[]}
    try:
        res['assigned'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['resolved_total'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True)['c']
        res['overdue'] = execute_query(f"SELECT COUNT(*) as c FROM tickets t WHERE assigned_to=%s AND (({dead} < %s::timestamp AND status IN ('Open','In Progress')) OR (updated_at > {dead} AND status IN ('Resolved','Closed')))", (uid, now), fetchone=True)['c']
        res['queue'] = get_tickets({'assigned_to': uid})
    except Exception as e: _debug_log('ENG_ERR', 'models.py', str(e), {})
    return res
