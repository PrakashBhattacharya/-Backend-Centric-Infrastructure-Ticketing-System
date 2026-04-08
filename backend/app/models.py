"""
Database models and helpers for InfraTick.
Uses SQLite for zero-config persistence.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config

DB_PATH = Config.DB_PATH

# Ensure instance directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# SLA deadlines in hours by priority
SLA_HOURS = {
    'Critical': 2,
    'High': 8,
    'Medium': 20,
    'Low': 50
}

def get_db():
    """Get a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all tables and seed admin if not exists."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('member', 'engineer', 'admin')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            service_area TEXT NOT NULL DEFAULT 'Other',
            environment TEXT NOT NULL DEFAULT 'Production',
            priority TEXT NOT NULL CHECK(priority IN ('Critical', 'High', 'Medium', 'Low')),
            status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
            sla_deadline TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_by INTEGER NOT NULL REFERENCES users(id),
            assigned_to INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            icon TEXT NOT NULL DEFAULT 'fa-info-circle',
            color TEXT NOT NULL DEFAULT '#3b82f6',
            danger INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER REFERENCES users(id),
            ticket_id INTEGER REFERENCES tickets(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    ''')

    # Seed admin account if not exists
    existing = cursor.execute(
        "SELECT id FROM users WHERE email = ?", ('manik102@gmail.com',)
    ).fetchone()

    if not existing:
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ('Manik', 'manik102@gmail.com', generate_password_hash('123456'), 'admin')
        )
        # Log admin creation
        admin_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (?, ?, ?, ?, ?)",
            ('System Initialized', 'Admin account created for Manik', 'fa-shield-alt', '#10b981', admin_id)
        )

    conn.commit()
    conn.close()

# ... (rest of the models.py logic remains identical)
# [TRUNCATED FOR BREVITY IN TOOL CALL, but I will write the full file content below]
def create_user(full_name, email, password, role):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (full_name, email, generate_password_hash(password), role.lower()))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.execute("INSERT INTO audit_logs (action, details, icon, color, user_id) VALUES (?, ?, ?, ?, ?)",
                    ('User Registered', f'{full_name} registered as {role}', 'fa-user-plus', '#3b82f6', user['id']))
        conn.commit()
        return dict(user)
    except sqlite3.IntegrityError: return None
    finally: conn.close()

def get_user_by_email(email):
    conn = get_db(); user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone(); conn.close(); return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db(); user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone(); conn.close(); return dict(user) if user else None

def get_all_users():
    conn = get_db(); users = conn.execute("SELECT id, full_name, email, role, created_at FROM users").fetchall(); conn.close(); return [dict(u) for u in users]

def get_engineers():
    conn = get_db(); engineers = conn.execute("SELECT id, full_name, email, role, created_at FROM users WHERE role = 'engineer'").fetchall(); conn.close(); return [dict(e) for e in engineers]

def create_ticket(subject, description, service_area, environment, priority, created_by):
    sla_hours = SLA_HOURS.get(priority, 50); now = datetime.utcnow(); sla_deadline = (now + timedelta(hours=sla_hours)).strftime('%Y-%m-%d %H:%M:%S'); now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO tickets (subject, description, service_area, environment, priority, status, sla_deadline, created_at, updated_at, created_by) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?)",
                   (subject, description, service_area, environment, priority, sla_deadline, now_str, now_str, created_by))
    ticket_id = cursor.lastrowid
    cursor.execute("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (?, ?, ?, ?, ?, ?)",
                   ('Ticket Created', f'#{ticket_id} — {subject} [{priority}]', 'fa-ticket-alt', '#3b82f6', created_by, ticket_id))
    conn.commit()
    ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone(); conn.close(); return dict(ticket)

def get_tickets(filters=None):
    conn = get_db()
    query = "SELECT t.*, u1.full_name as creator_name, u1.email as creator_email, u2.full_name as assignee_name, u2.email as assignee_email FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id"
    conditions = []; params = []
    if filters:
        for k, v in filters.items(): conditions.append(f"t.{k} = ?"); params.append(v)
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY t.created_at DESC"
    tickets = conn.execute(query, params).fetchall(); conn.close(); return [dict(t) for t in tickets]

def get_ticket_by_id(ticket_id):
    conn = get_db(); ticket = conn.execute("SELECT t.*, u1.full_name as creator_name, u2.full_name as assignee_name FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id WHERE t.id = ?", (ticket_id,)).fetchone(); conn.close(); return dict(ticket) if ticket else None

def update_ticket_status(ticket_id, new_status, user_id):
    conn = get_db(); now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, ticket_id))
    icon_map = {'In Progress': ('fa-spinner', '#3b82f6'), 'Resolved': ('fa-check-circle', '#10b981'), 'Closed': ('fa-times-circle', '#64748b'), 'Open': ('fa-folder-open', '#f59e0b')}
    icon, color = icon_map.get(new_status, ('fa-edit', '#3b82f6'))
    conn.execute("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (?, ?, ?, ?, ?, ?)", (f'Status → {new_status}', f'Ticket #{ticket_id} status changed to {new_status}', icon, color, user_id, ticket_id))
    conn.commit(); conn.close()

def assign_ticket(ticket_id, engineer_id, admin_id):
    conn = get_db(); cursor = conn.cursor()
    now_dt = datetime.utcnow()
    now = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Verify engineer exists and is an engineer
    engineer = cursor.execute("SELECT full_name, role FROM users WHERE id = ?", (engineer_id,)).fetchone()
    if not engineer or engineer['role'].lower() != 'engineer':
        conn.close()
        return False

    # Get ticket details to recalculate SLA
    ticket = cursor.execute("SELECT priority FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        return False
        
    priority = ticket['priority']
    sla_hours = SLA_HOURS.get(priority, 50)
    new_sla_deadline = (now_dt + timedelta(hours=sla_hours)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("UPDATE tickets SET assigned_to = ?, status = 'In Progress', updated_at = ?, sla_deadline = ? WHERE id = ?", (engineer_id, now, new_sla_deadline, ticket_id))
    engineer_name = engineer['full_name']
    cursor.execute("INSERT INTO audit_logs (action, details, icon, color, user_id, ticket_id) VALUES (?, ?, ?, ?, ?, ?)", ('Ticket Assigned', f'Ticket #{ticket_id} assigned to {engineer_name}', 'fa-user-cog', '#8b5cf6', admin_id, ticket_id))
    conn.commit(); conn.close()
    return True

def add_comment(ticket_id, user_id, text):
    conn = get_db(); conn.execute("INSERT INTO comments (ticket_id, user_id, text) VALUES (?, ?, ?)", (ticket_id, user_id, text)); conn.commit(); conn.close()

def get_comments(ticket_id):
    conn = get_db(); comments = conn.execute("SELECT c.*, u.full_name as user_name, u.role as user_role FROM comments c JOIN users u ON c.user_id = u.id WHERE c.ticket_id = ? ORDER BY c.created_at ASC", (ticket_id,)).fetchall(); conn.close(); return [dict(c) for c in comments]

def get_audit_logs(limit=20):
    conn = get_db(); logs = conn.execute("SELECT a.*, u.full_name as user_name FROM audit_logs a LEFT JOIN users u ON a.user_id = u.id ORDER BY a.created_at DESC LIMIT ?", (limit,)).fetchall(); conn.close(); return [dict(l) for l in logs]

def add_audit_log(action, details, icon='fa-info-circle', color='#3b82f6', danger=False, user_id=None, ticket_id=None):
    conn = get_db(); conn.execute("INSERT INTO audit_logs (action, details, icon, color, danger, user_id, ticket_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (action, details, icon, color, 1 if danger else 0, user_id, ticket_id)); conn.commit(); conn.close()

def get_member_stats(user_id):
    conn = get_db(); c = conn.cursor(); now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    active = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND status IN ('Open', 'In Progress')", (user_id,)).fetchone()[0]
    resolved = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND status IN ('Resolved', 'Closed')", (user_id,)).fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ?", (user_id,)).fetchone()[0]
    urgent = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND priority IN ('Critical', 'High') AND status IN ('Open', 'In Progress')", (user_id,)).fetchone()[0]
    breached = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND sla_deadline < ? AND status NOT IN ('Resolved', 'Closed')", (user_id, now)).fetchone()[0]
    sla_met = c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (user_id,)).fetchone()[0]
    sla_pct = round((sla_met / resolved * 100), 1) if resolved > 0 else 0
    priority_counts = {p: c.execute("SELECT COUNT(*) FROM tickets WHERE created_by = ? AND priority = ?", (user_id, p)).fetchone()[0] for p in ['Critical', 'High', 'Medium', 'Low']}
    tickets = c.execute("SELECT t.*, u.full_name as assignee_name FROM tickets t LEFT JOIN users u ON t.assigned_to = u.id WHERE t.created_by = ? ORDER BY t.created_at DESC", (user_id,)).fetchall()
    conn.close()
    return {'active': active, 'resolved': resolved, 'total': total, 'urgent': urgent, 'breached': breached, 'sla_pct': sla_pct, 'priorityData': list(priority_counts.values()), 'tickets': [dict(t) for t in tickets]}

def get_engineer_stats(user_id):
    conn = get_db(); c = conn.cursor(); now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    assigned = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Open', 'In Progress')", (user_id,)).fetchone()[0]
    overdue = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND sla_deadline < ? AND status NOT IN ('Resolved', 'Closed')", (user_id, now)).fetchone()[0]
    resolved_total = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Resolved', 'Closed')", (user_id,)).fetchone()[0]
    sla_met = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (user_id,)).fetchone()[0]
    sla_pct = round((sla_met / resolved_total * 100), 1) if resolved_total > 0 else 0
    queue = c.execute("SELECT t.*, u.full_name as creator_name FROM tickets t LEFT JOIN users u ON t.created_by = u.id WHERE t.assigned_to = ? AND t.status IN ('Open', 'In Progress') ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, t.created_at ASC", (user_id,)).fetchall()
    resolved_list = c.execute("SELECT t.*, u.full_name as creator_name FROM tickets t LEFT JOIN users u ON t.created_by = u.id WHERE t.assigned_to = ? AND t.status IN ('Resolved', 'Closed') ORDER BY t.updated_at DESC LIMIT 10", (user_id,)).fetchall()
    conn.close()
    return {'assigned': assigned, 'overdue': overdue, 'resolved_total': resolved_total, 'sla_pct': sla_pct, 'queue': [dict(t) for t in queue], 'resolved_list': [dict(t) for t in resolved_list]}

def get_admin_stats():
    conn = get_db(); c = conn.cursor(); now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    total_open = c.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open', 'In Progress')").fetchone()[0]
    breaches_today = c.execute("SELECT COUNT(*) FROM tickets WHERE sla_deadline < ? AND status NOT IN ('Resolved', 'Closed')", (now,)).fetchone()[0]
    escalated = c.execute("SELECT COUNT(*) FROM tickets WHERE priority = 'Critical' AND status IN ('Open', 'In Progress')").fetchone()[0]
    total_resolved = c.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved', 'Closed')").fetchone()[0]
    total_all = c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    sla_met = c.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline").fetchone()[0]
    near_breach = c.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open', 'In Progress') AND sla_deadline > ? AND sla_deadline < datetime(?, '+2 hours')", (now, now)).fetchone()[0]
    aging = [c.execute(f"SELECT COUNT(*) FROM tickets WHERE status IN ('Open', 'In Progress') AND {q}").fetchone()[0] for q in ["created_at >= datetime('now', '-1 day')", "created_at < datetime('now', '-1 day') AND created_at >= datetime('now', '-3 days')", "created_at < datetime('now', '-3 days') AND created_at >= datetime('now', '-7 days')", "created_at < datetime('now', '-7 days')"]]
    services = ['Database', 'Networking', 'Compute / VM', 'Security / IAM', 'Storage']
    service_counts = [c.execute("SELECT COUNT(*) FROM tickets WHERE service_area = ? AND status IN ('Open', 'In Progress')", (svc,)).fetchone()[0] for svc in services]
    engineers = c.execute("SELECT id, full_name, email FROM users WHERE role = 'engineer'").fetchall()
    engineer_data = []
    for eng in engineers:
        ea, er = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Open', 'In Progress')", (eng['id'],)).fetchone()[0], c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Resolved', 'Closed')", (eng['id'],)).fetchone()[0]
        esm = c.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ('Resolved', 'Closed') AND updated_at <= sla_deadline", (eng['id'],)).fetchone()[0]
        esp = round((esm / er * 100)) if er > 0 else 0
        engineer_data.append({'id': eng['id'], 'name': eng['full_name'], 'assigned': ea, 'resolved': er, 'mttr': '-', 'sla': esp, 'reopens': '0%', 'status': 'excellent' if esp >= 95 else 'good' if esp >= 85 else 'warning' if esp >= 70 else 'critical'})
    all_tickets = c.execute("SELECT t.*, u1.full_name as creator_name, u2.full_name as assignee_name FROM tickets t LEFT JOIN users u1 ON t.created_by = u1.id LEFT JOIN users u2 ON t.assigned_to = u2.id ORDER BY t.created_at DESC").fetchall()
    conn.close()
    return {'total_open': total_open, 'breaches_today': breaches_today, 'escalated': escalated, 'total_resolved': total_resolved, 'total_all': total_all, 'reopen_rate': 0, 'slaComplianceData': [sla_met, near_breach, max(0, total_resolved - sla_met)], 'agingData': aging, 'backlogTrendData': [total_open, 0,0,0,0,0], 'serviceImpactData': service_counts, 'regionLoadData': [total_open, 0,0,0], 'engineers': engineer_data, 'all_tickets': [dict(t) for t in all_tickets]}
