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
        cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id SERIAL PRIMARY KEY, subject TEXT NOT NULL, description TEXT NOT NULL DEFAULT \'\', service_area TEXT NOT NULL DEFAULT \'Other\', environment TEXT NOT NULL DEFAULT \'Production\', priority TEXT NOT NULL CHECK(priority IN (\'Critical\', \'High\', \'Medium\', \'Low\')), status TEXT NOT NULL DEFAULT \'Open\' CHECK(status IN (\'Open\', \'In Progress\', \'Pending Approval\', \'Resolved\', \'Closed\')), sla_deadline TIMESTAMP NOT NULL, resolved_at TIMESTAMP, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, created_by INTEGER NOT NULL REFERENCES users(id), assigned_to INTEGER REFERENCES users(id));')
        cursor.execute('CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);')
        cursor.execute('CREATE TABLE IF NOT EXISTS audit_logs (id SERIAL PRIMARY KEY, action TEXT NOT NULL, details TEXT NOT NULL DEFAULT \'\', icon TEXT NOT NULL DEFAULT \'fa-info-circle\', color TEXT NOT NULL DEFAULT \'#3b82f6\', danger INTEGER NOT NULL DEFAULT 0, user_id INTEGER REFERENCES users(id), ticket_id INTEGER REFERENCES tickets(id), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);')

        # Migration: add resolved_at column if it doesn't exist yet
        try:
            cursor.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;")
            conn.commit()
        except Exception:
            conn.rollback()

        # Migration: widen the status CHECK constraint to include Pending Approval
        # Drop ALL check constraints on the status column by querying the catalog,
        # then re-add the correct one — handles any auto-generated constraint name.
        try:
            cursor.execute("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'tickets'::regclass
                AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%status%'
            """)
            rows = cursor.fetchall()
            for row in rows:
                cursor.execute(f'ALTER TABLE tickets DROP CONSTRAINT IF EXISTS "{row[0]}"')
            cursor.execute(
                "ALTER TABLE tickets ADD CONSTRAINT tickets_status_check "
                "CHECK(status IN ('Open', 'In Progress', 'Pending Approval', 'Resolved', 'Closed'))"
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] status constraint migration skipped: {e}")

        # Create chat tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_groups (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_group_members (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL REFERENCES chat_groups(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, user_id)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id),
                recipient_id INTEGER REFERENCES users(id),
                group_id INTEGER REFERENCES chat_groups(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

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
    # When engineer submits for approval, record resolved_at so SLA timer is anchored
    if new_status == 'Pending Approval':
        execute_query(
            "UPDATE tickets SET status = %s, resolved_at = %s, rejection_note = '', updated_at = %s WHERE id = %s",
            (new_status, now, now, ticket_id), commit=True
        )
    else:
        execute_query(
            "UPDATE tickets SET status = %s, updated_at = %s WHERE id = %s",
            (new_status, now, ticket_id), commit=True
        )
    im = {
        'In Progress':      ('fa-spinner',      '#3b82f6'),
        'Pending Approval': ('fa-hourglass-half','#f59e0b'),
        'Resolved':         ('fa-check-circle', '#10b981'),
        'Closed':           ('fa-times-circle', '#64748b'),
    }
    icon, col = im.get(new_status, ('fa-edit', '#3b82f6'))
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (f'Status → {new_status}', f'Ticket #{ticket_id} status changed to {new_status}', icon, col, user_id, ticket_id),
        commit=True
    )

def approve_ticket(ticket_id, admin_id):
    """Admin approves a Pending Approval ticket → marks it Resolved."""
    ticket = get_ticket_by_id(ticket_id)
    if not ticket or ticket['status'] != 'Pending Approval':
        return False
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query(
        "UPDATE tickets SET status = 'Resolved', updated_at = %s WHERE id = %s",
        (now, ticket_id), commit=True
    )
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)",
        ('Resolution Approved', f'Ticket #{ticket_id} approved and marked Resolved by admin',
         'fa-check-double', '#10b981', admin_id, ticket_id),
        commit=True
    )
    return True

def reject_ticket(ticket_id, admin_id, reason=''):
    """Admin rejects a Pending Approval ticket → sends it back to In Progress.
    The SLA timer continues from resolved_at so the engineer is penalised for the delay."""
    ticket = get_ticket_by_id(ticket_id)
    if not ticket or ticket['status'] != 'Pending Approval':
        return False
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query(
        "UPDATE tickets SET status = 'In Progress', rejection_note = %s, updated_at = %s WHERE id = %s",
        (reason or '', now, ticket_id), commit=True
    )
    detail = f'Ticket #{ticket_id} resolution rejected — sent back to engineer.'
    if reason:
        detail += f' Reason: {reason}'
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, danger, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        ('Resolution Rejected', detail, 'fa-times-circle', '#ef4444', 1, admin_id, ticket_id),
        commit=True
    )
    return True

def assign_ticket(tid, eid, aid):
    eng = execute_query("SELECT full_name FROM users WHERE id = %s AND role = 'engineer'", (eid,), fetchone=True)
    if not eng: return False
    execute_query("UPDATE tickets SET assigned_to = %s, status = 'In Progress', updated_at = %s WHERE id = %s", (eid, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), tid), commit=True)
    execute_query("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s)", ('Ticket Assigned', f'Ticket #{tid} assigned to {eng["full_name"]}', 'fa-user-cog', '#8b5cf6', aid, tid), commit=True)
    return True

def get_admin_stats():
    now = datetime.utcnow()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = {
        'total_open': 0, 'breaches_today': 0, 'escalated': 0,
        'total_resolved': 0, 'total_all': 0, 'mttr': '0.0h',
        'avg_aging': '0.0d', 'reopen_rate': 0, 'pending_approval': 0, 'pending_sla_requests': 0,
        'slaComplianceData': [0, 0, 0],
        'agingData': [0, 0, 0, 0],
        'serviceImpactData': [0, 0, 0, 0, 0],
        'regionLoadData': [0, 0, 0, 0],
        'backlogTrendData': [0, 0, 0, 0, 0, 0, 0],
        'engineers': [], 'all_tickets': []
    }
    try:
        res['total_open'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open', 'In Progress', 'Pending Approval')", fetchone=True)['count']
        res['pending_approval'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status = 'Pending Approval'", fetchone=True)['count']
        res['pending_sla_requests'] = execute_query("SELECT COUNT(*) as count FROM sla_extension_requests WHERE status = 'Pending'", fetchone=True)['count']
        res['total_all'] = execute_query("SELECT COUNT(*) as count FROM tickets", fetchone=True)['count']
        res['total_resolved'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)['count']

        b1 = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open', 'In Progress') AND {dead} < %s::timestamp", (now_str,), fetchone=True)['count']
        b2 = execute_query(f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Resolved', 'Closed') AND updated_at > {dead}", fetchone=True)['count']
        res['breaches_today'] = b1 + b2
        res['escalated'] = execute_query("SELECT COUNT(*) as count FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'In Progress')", fetchone=True)['count']

        # MTTR
        m_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE status IN ('Resolved', 'Closed')", fetchone=True)
        res['mttr'] = f"{round(float(m_row['mttr'] or 0), 1)}h"

        # Average aging of open tickets in days
        aging_row = execute_query("SELECT AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/86400) as avg_age FROM tickets WHERE status IN ('Open', 'In Progress')", fetchone=True)
        res['avg_aging'] = f"{round(float(aging_row['avg_age'] or 0), 1)}d"

        # Reopen rate: tickets that went from Resolved back to Open/In Progress
        # Approximated as: tickets with status Open/In Progress that have been updated after creation
        total_res = res['total_resolved']
        if total_res > 0:
            reopened = execute_query(
                "SELECT COUNT(*) as count FROM tickets WHERE status IN ('Open','In Progress') AND updated_at > created_at + interval '1 minute'",
                fetchone=True
            )['count']
            res['reopen_rate'] = round((reopened / total_res) * 100, 1)

        # SLA Compliance breakdown for open tickets
        total_open = res['total_open']
        if total_open > 0:
            breached_open = execute_query(
                f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open','In Progress') AND {dead} < %s::timestamp",
                (now_str,), fetchone=True
            )['count']
            # Near breach = within 20% of SLA window remaining
            near_breach = execute_query(
                f"SELECT COUNT(*) as count FROM tickets t WHERE status IN ('Open','In Progress') "
                f"AND {dead} >= %s::timestamp "
                f"AND {dead} < (%s::timestamp + interval '4 hours')",
                (now_str, now_str), fetchone=True
            )['count']
            compliant = max(0, total_open - breached_open - near_breach)
            res['slaComplianceData'] = [compliant, near_breach, breached_open]
        else:
            res['slaComplianceData'] = [0, 0, 0]

        # Ticket aging distribution (open tickets only)
        aging_buckets = [0, 0, 0, 0]
        open_tickets_ages = execute_query(
            "SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/3600 as age_hours FROM tickets WHERE status IN ('Open','In Progress')"
        ) or []
        for row in open_tickets_ages:
            h = float(row['age_hours'] or 0)
            if h < 24:
                aging_buckets[0] += 1
            elif h < 72:
                aging_buckets[1] += 1
            elif h < 168:
                aging_buckets[2] += 1
            else:
                aging_buckets[3] += 1
        res['agingData'] = aging_buckets

        # Service impact
        svc_map = {'Database': 0, 'Networking': 1, 'Compute / VM': 2, 'Security / IAM': 3, 'Storage': 4}
        svcs = execute_query("SELECT service_area, COUNT(*) as c FROM tickets GROUP BY service_area")
        for s in (svcs or []):
            if s['service_area'] in svc_map:
                res['serviceImpactData'][svc_map[s['service_area']]] = s['c']

        # Region/environment load
        env_map = {'Production': 0, 'Staging': 1, 'Development': 2, 'Local': 3}
        envs = execute_query("SELECT environment, COUNT(*) as c FROM tickets GROUP BY environment")
        for e in (envs or []):
            if e['environment'] in env_map:
                res['regionLoadData'][env_map[e['environment']]] = e['c']

        # Backlog trend: new tickets per day for last 7 days
        trend = [0, 0, 0, 0, 0, 0, 0]
        for i in range(7):
            day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            row = execute_query(
                "SELECT COUNT(*) as c FROM tickets WHERE created_at >= %s::timestamp AND created_at < %s::timestamp",
                (day_start.strftime('%Y-%m-%d %H:%M:%S'), day_end.strftime('%Y-%m-%d %H:%M:%S')),
                fetchone=True
            )
            trend[i] = row['c'] if row else 0
        res['backlogTrendData'] = trend

        # Engineer performance matrix
        engineers = get_engineers()
        eng_stats = []
        for eng in engineers:
            eid = eng['id']
            eng_dead = _effective_deadline_sql('t')
            e_assigned = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Open','In Progress')", (eid,), fetchone=True)['c']
            e_resolved = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')", (eid,), fetchone=True)['c']
            e_total = e_assigned + e_resolved

            # MTTR for this engineer
            e_mttr_row = execute_query(
                "SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')",
                (eid,), fetchone=True
            )
            e_mttr = round(float(e_mttr_row['mttr'] or 0), 1) if e_mttr_row else 0

            # SLA compliance for this engineer
            e_breached = execute_query(
                f"SELECT COUNT(*) as c FROM tickets t WHERE assigned_to=%s AND (({eng_dead} < %s::timestamp AND status IN ('Open','In Progress')) OR (updated_at > {eng_dead} AND status IN ('Resolved','Closed')))",
                (eid, now_str), fetchone=True
            )['c']
            e_sla = round(((e_total - e_breached) / e_total) * 100) if e_total > 0 else 100

            # Determine status label
            if e_sla >= 90 and e_assigned <= 5:
                status = 'Excellent'
            elif e_sla >= 70 or e_assigned <= 10:
                status = 'Warning'
            else:
                status = 'Critical'

            eng_stats.append({
                'id': eid,
                'name': eng['full_name'],
                'assigned': e_assigned,
                'resolved': e_resolved,
                'mttr': f"{e_mttr}h",
                'sla': e_sla,
                'reopens': '0%',
                'status': status
            })
        res['engineers'] = eng_stats

        res['all_tickets'] = get_tickets()
    except Exception as e:
        _debug_log('ADMIN_ERR', 'models.py', str(e), {})
    return res

def get_member_stats(uid):
    now = datetime.utcnow()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = {
        'active': 0, 'resolved': 0, 'total': 0, 'urgent': 0,
        'breached': 0, 'sla_pct': 0, 'mttr': '0.0h',
        'priorityData': [0, 0, 0, 0],
        'backlogTrendData': [0, 0, 0, 0, 0, 0, 0],
        'tickets': []
    }
    try:
        res['active'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['resolved'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True)['c']
        res['total'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s", (uid,), fetchone=True)['c']
        res['urgent'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND priority='Critical' AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['breached'] = execute_query(
            f"SELECT COUNT(*) as c FROM tickets t WHERE created_by=%s AND (({dead} < %s::timestamp AND status IN ('Open','In Progress')) OR (updated_at > {dead} AND status IN ('Resolved','Closed')))",
            (uid, now_str), fetchone=True
        )['c']

        # SLA percentage
        total = res['total']
        res['sla_pct'] = round(((total - res['breached']) / total) * 100) if total > 0 else 100

        # MTTR for this member's resolved tickets
        mttr_row = execute_query(
            "SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE created_by=%s AND status IN ('Resolved','Closed')",
            (uid,), fetchone=True
        )
        res['mttr'] = f"{round(float(mttr_row['mttr'] or 0), 1)}h" if mttr_row else '0.0h'

        # Priority breakdown
        prio_map = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        prios = execute_query("SELECT priority, COUNT(*) as c FROM tickets WHERE created_by=%s GROUP BY priority", (uid,))
        for p in (prios or []):
            if p['priority'] in prio_map:
                res['priorityData'][prio_map[p['priority']]] = p['c']

        # Backlog trend: tickets submitted per day for last 7 days
        trend = [0, 0, 0, 0, 0, 0, 0]
        for i in range(7):
            day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            row = execute_query(
                "SELECT COUNT(*) as c FROM tickets WHERE created_by=%s AND created_at >= %s::timestamp AND created_at < %s::timestamp",
                (uid, day_start.strftime('%Y-%m-%d %H:%M:%S'), day_end.strftime('%Y-%m-%d %H:%M:%S')),
                fetchone=True
            )
            trend[i] = row['c'] if row else 0
        res['backlogTrendData'] = trend

        res['tickets'] = get_tickets({'created_by': uid})
    except Exception as e:
        _debug_log('MEM_ERR', 'models.py', str(e), {})
    return res

def add_audit_log(action, details, icon='fa-info-circle', color='#3b82f6', user_id=None, ticket_id=None, danger=0):
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, danger, user_id, ticket_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (action, details, icon, color, danger, user_id, ticket_id),
        commit=True
    )

def get_audit_logs(limit=20):
    return execute_query(
        "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT %s",
        (limit,)
    ) or []

def add_comment(ticket_id, user_id, text):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query(
        "INSERT INTO comments (ticket_id, user_id, text, created_at) VALUES (%s, %s, %s, %s)",
        (ticket_id, user_id, text, now),
        commit=True
    )

def get_comments(ticket_id):
    return execute_query(
        "SELECT c.*, u.full_name as author_name FROM comments c JOIN users u ON c.user_id = u.id WHERE c.ticket_id = %s ORDER BY c.created_at ASC",
        (ticket_id,)
    ) or []

# ─── SLA Extension Requests ──────────────────────────────────────────────────

def request_sla_extension(ticket_id, engineer_id, requested_hours, reason):
    """Engineer requests more time on a ticket."""
    # Only one pending request per ticket at a time
    existing = execute_query(
        "SELECT id FROM sla_extension_requests WHERE ticket_id=%s AND status='Pending'",
        (ticket_id,), fetchone=True
    )
    if existing:
        return None, 'A pending SLA extension request already exists for this ticket.'
    row = execute_query(
        "INSERT INTO sla_extension_requests (ticket_id, engineer_id, requested_hours, reason) "
        "VALUES (%s, %s, %s, %s) RETURNING *",
        (ticket_id, engineer_id, requested_hours, reason), commit=True, fetchone=True
    )
    if row:
        execute_query(
            "INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s,%s,%s,%s,%s,%s)",
            ('SLA Extension Requested',
             f'Ticket #{ticket_id} — engineer requested +{requested_hours}h. Reason: {reason}',
             'fa-clock', '#f59e0b', engineer_id, ticket_id),
            commit=True
        )
    return row, None

def get_sla_extension_requests(status=None, ticket_id=None):
    """Fetch SLA extension requests with engineer and ticket info."""
    query = (
        "SELECT r.*, u.full_name as engineer_name, t.subject as ticket_subject, "
        "t.sla_deadline, t.priority "
        "FROM sla_extension_requests r "
        "JOIN users u ON r.engineer_id = u.id "
        "JOIN tickets t ON r.ticket_id = t.id"
    )
    params = []
    conditions = []
    if status:
        conditions.append("r.status = %s")
        params.append(status)
    if ticket_id:
        conditions.append("r.ticket_id = %s")
        params.append(ticket_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.created_at DESC"
    return execute_query(query, tuple(params)) or []

def approve_sla_extension(request_id, admin_id, admin_note=''):
    """Admin approves — extends the ticket's sla_deadline by requested_hours."""
    req = execute_query(
        "SELECT * FROM sla_extension_requests WHERE id=%s AND status='Pending'",
        (request_id,), fetchone=True
    )
    if not req:
        return False, 'Request not found or already resolved.'
    now = datetime.utcnow()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    # Extend deadline from current deadline (not from now)
    execute_query(
        "UPDATE tickets SET sla_deadline = sla_deadline + (%s || ' hours')::interval, updated_at = %s WHERE id = %s",
        (str(req['requested_hours']), now_str, req['ticket_id']), commit=True
    )
    execute_query(
        "UPDATE sla_extension_requests SET status='Approved', admin_note=%s, resolved_at=%s WHERE id=%s",
        (admin_note, now_str, request_id), commit=True
    )
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s,%s,%s,%s,%s,%s)",
        ('SLA Extension Approved',
         f'Ticket #{req["ticket_id"]} SLA extended by {req["requested_hours"]}h.',
         'fa-clock', '#10b981', admin_id, req['ticket_id']),
        commit=True
    )
    return True, None

def reject_sla_extension(request_id, admin_id, admin_note=''):
    """Admin rejects — deadline unchanged."""
    req = execute_query(
        "SELECT * FROM sla_extension_requests WHERE id=%s AND status='Pending'",
        (request_id,), fetchone=True
    )
    if not req:
        return False, 'Request not found or already resolved.'
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    execute_query(
        "UPDATE sla_extension_requests SET status='Rejected', admin_note=%s, resolved_at=%s WHERE id=%s",
        (admin_note, now_str, request_id), commit=True
    )
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, danger, user_id, ticket_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        ('SLA Extension Rejected',
         f'Ticket #{req["ticket_id"]} SLA extension request rejected.',
         'fa-clock', '#ef4444', 1, admin_id, req['ticket_id']),
        commit=True
    )
    return True, None

# ─── Ticket Attachments ──────────────────────────────────────────────────────

def add_attachment(ticket_id, user_id, file_name, mime_type, file_data):
    """Store a base64-encoded file attachment for a ticket."""
    execute_query(
        "INSERT INTO ticket_attachments (ticket_id, user_id, file_name, mime_type, file_data) "
        "VALUES (%s, %s, %s, %s, %s)",
        (ticket_id, user_id, file_name, mime_type, file_data), commit=True
    )
    execute_query(
        "INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (%s,%s,%s,%s,%s,%s)",
        ('File Attached', f'Attached {file_name} to ticket #{ticket_id}',
         'fa-paperclip', '#6b7280', user_id, ticket_id), commit=True
    )

def get_ticket_attachments(ticket_id):
    """Return attachment metadata (no file_data) for a ticket."""
    rows = execute_query(
        "SELECT a.id, a.file_name, a.mime_type, a.created_at, a.user_id, u.full_name as user_name "
        "FROM ticket_attachments a JOIN users u ON a.user_id = u.id "
        "WHERE a.ticket_id = %s ORDER BY a.created_at ASC",
        (ticket_id,)
    ) or []
    return rows

def get_attachment_data(attachment_id):
    """Return the full attachment including base64 file_data."""
    return execute_query(
        "SELECT id, file_name, mime_type, file_data FROM ticket_attachments WHERE id = %s",
        (attachment_id,), fetchone=True
    )

def get_engineer_stats(uid):
    now = datetime.utcnow()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    dead = _effective_deadline_sql('t')
    res = {
        'assigned': 0, 'overdue': 0, 'resolved_total': 0,
        'sla_pct': 0, 'mttr': '0.0h', 'mttr_trend': [0, 0, 0, 0, 0],
        'res_score': 0.0,
        'queue': [], 'resolved_list': []
    }
    try:
        res['assigned'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Open','In Progress')", (uid,), fetchone=True)['c']
        res['resolved_total'] = execute_query("SELECT COUNT(*) as c FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')", (uid,), fetchone=True)['c']
        res['overdue'] = execute_query(
            f"SELECT COUNT(*) as c FROM tickets t WHERE assigned_to=%s AND (({dead} < %s::timestamp AND status IN ('Open','In Progress')) OR (updated_at > {dead} AND status IN ('Resolved','Closed')))",
            (uid, now_str), fetchone=True
        )['c']

        # MTTR
        mttr_row = execute_query(
            "SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as mttr FROM tickets WHERE assigned_to=%s AND status IN ('Resolved','Closed')",
            (uid,), fetchone=True
        )
        mttr_val = round(float(mttr_row['mttr'] or 0), 1) if mttr_row else 0
        res['mttr'] = f"{mttr_val}h"

        # SLA percentage
        total = res['assigned'] + res['resolved_total']
        res['sla_pct'] = round(((total - res['overdue']) / total) * 100) if total > 0 else 100

        # Resolution Score (0–10): composite of three factors
        # - SLA compliance (40%): how many tickets met SLA
        # - Resolution ratio (30%): resolved vs total assigned
        # - MTTR efficiency (30%): lower MTTR = higher score, capped at SLA baseline of 8h
        sla_score = (res['sla_pct'] / 100) * 4.0
        resolution_ratio = (res['resolved_total'] / total) if total > 0 else 0
        ratio_score = resolution_ratio * 3.0
        mttr_efficiency = max(0.0, 1.0 - (mttr_val / 8.0)) if mttr_val > 0 else 1.0
        mttr_score = mttr_efficiency * 3.0
        res['res_score'] = round(min(10.0, sla_score + ratio_score + mttr_score), 1)

        # MTTR trend: average resolution time per day for last 5 days
        mttr_trend = []
        for i in range(5):
            day_start = (now - timedelta(days=4 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            row = execute_query(
                "SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as avg_mttr FROM tickets "
                "WHERE assigned_to=%s AND status IN ('Resolved','Closed') "
                "AND updated_at >= %s::timestamp AND updated_at < %s::timestamp",
                (uid, day_start.strftime('%Y-%m-%d %H:%M:%S'), day_end.strftime('%Y-%m-%d %H:%M:%S')),
                fetchone=True
            )
            mttr_trend.append(round(float(row['avg_mttr'] or 0), 1) if row and row['avg_mttr'] else 0)
        res['mttr_trend'] = mttr_trend

        # Active queue (Open + In Progress + Pending Approval)
        all_assigned = get_tickets({'assigned_to': uid})
        res['queue'] = [t for t in all_assigned if t['status'] in ('Open', 'In Progress', 'Pending Approval')]
        res['resolved_list'] = [t for t in all_assigned if t['status'] in ('Resolved', 'Closed')]
    except Exception as e:
        _debug_log('ENG_ERR', 'models.py', str(e), {})
    return res


# ─── SLA Extension Requests ──────────────────────────────────────────────────