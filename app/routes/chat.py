"""
Chat API blueprint — private messages and group chats.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
from .auth import token_required
from ..models import execute_query, get_all_users

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


# ─── Users list (for starting private chats) ─────────────────────────────────

@chat_bp.route('/users', methods=['GET'])
@token_required
def list_users(current_user):
    """Return all users except the current user."""
    users = execute_query(
        "SELECT id, full_name, email, role FROM users WHERE id != %s ORDER BY full_name",
        (current_user['id'],)
    ) or []
    return jsonify({'success': True, 'users': users})


# ─── Private Messages ─────────────────────────────────────────────────────────

@chat_bp.route('/private/<int:other_user_id>', methods=['GET'])
@token_required
def get_private_messages(current_user, other_user_id):
    """Fetch private message history between current user and another user."""
    since = request.args.get('since')  # ISO timestamp for polling
    uid = current_user['id']

    if since:
        msgs = execute_query(
            "SELECT m.*, u.full_name as sender_name, u.role as sender_role "
            "FROM chat_messages m JOIN users u ON m.sender_id = u.id "
            "WHERE m.group_id IS NULL "
            "AND ((m.sender_id = %s AND m.recipient_id = %s) OR (m.sender_id = %s AND m.recipient_id = %s)) "
            "AND m.created_at > %s::timestamp "
            "ORDER BY m.created_at ASC",
            (uid, other_user_id, other_user_id, uid, since)
        ) or []
    else:
        msgs = execute_query(
            "SELECT m.*, u.full_name as sender_name, u.role as sender_role "
            "FROM chat_messages m JOIN users u ON m.sender_id = u.id "
            "WHERE m.group_id IS NULL "
            "AND ((m.sender_id = %s AND m.recipient_id = %s) OR (m.sender_id = %s AND m.recipient_id = %s)) "
            "ORDER BY m.created_at ASC LIMIT 100",
            (uid, other_user_id, other_user_id, uid)
        ) or []
    return jsonify({'success': True, 'messages': msgs})


@chat_bp.route('/private/<int:other_user_id>', methods=['POST'])
@token_required
def send_private_message(current_user, other_user_id):
    """Send a private message (with optional file attachment) to another user."""
    data = request.json or {}
    text = (data.get('text') or '').strip()
    file_name = data.get('file_name')
    file_type = data.get('file_type', 'application/octet-stream')
    file_data = data.get('file_data')

    if not text and not file_data:
        return jsonify({'message': 'Message or file is required.'}), 400

    recipient = execute_query("SELECT id FROM users WHERE id = %s", (other_user_id,), fetchone=True)
    if not recipient:
        return jsonify({'message': 'Recipient not found.'}), 404

    msg_text = text or f'📎 {file_name}'
    msg = execute_query(
        "INSERT INTO chat_messages (sender_id, recipient_id, text, file_name, file_type, file_data) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, sender_id, recipient_id, text, file_name, file_type, created_at",
        (current_user['id'], other_user_id, msg_text, file_name, file_type, file_data), commit=True, fetchone=True
    )
    return jsonify({'success': True, 'message': msg}), 201


# ─── Inbox (list of private conversations) ───────────────────────────────────

@chat_bp.route('/inbox', methods=['GET'])
@token_required
def get_inbox(current_user):
    """Return the latest message per private conversation for the current user."""
    uid = current_user['id']
    rows = execute_query(
        """
        SELECT DISTINCT ON (other_id)
            other_id,
            other_name,
            other_role,
            last_text,
            last_at
        FROM (
            SELECT
                CASE WHEN m.sender_id = %s THEN m.recipient_id ELSE m.sender_id END AS other_id,
                CASE WHEN m.sender_id = %s THEN ru.full_name ELSE su.full_name END AS other_name,
                CASE WHEN m.sender_id = %s THEN ru.role ELSE su.role END AS other_role,
                m.text AS last_text,
                m.created_at AS last_at
            FROM chat_messages m
            JOIN users su ON m.sender_id = su.id
            JOIN users ru ON m.recipient_id = ru.id
            WHERE m.group_id IS NULL
              AND (m.sender_id = %s OR m.recipient_id = %s)
        ) sub
        ORDER BY other_id, last_at DESC
        """,
        (uid, uid, uid, uid, uid)
    ) or []
    # Sort by last_at descending
    rows.sort(key=lambda r: r.get('last_at') or '', reverse=True)
    return jsonify({'success': True, 'conversations': rows})


# ─── Group Chats ──────────────────────────────────────────────────────────────

@chat_bp.route('/groups', methods=['GET'])
@token_required
def list_groups(current_user):
    """Return all groups the current user is a member of."""
    uid = current_user['id']
    groups = execute_query(
        """
        SELECT g.id, g.name, g.description, g.created_by, g.created_at,
               u.full_name as creator_name,
               (SELECT COUNT(*) FROM chat_group_members WHERE group_id = g.id) as member_count,
               (SELECT text FROM chat_messages WHERE group_id = g.id ORDER BY created_at DESC LIMIT 1) as last_message,
               (SELECT created_at FROM chat_messages WHERE group_id = g.id ORDER BY created_at DESC LIMIT 1) as last_at
        FROM chat_groups g
        JOIN users u ON g.created_by = u.id
        JOIN chat_group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = %s
        ORDER BY COALESCE(
            (SELECT created_at FROM chat_messages WHERE group_id = g.id ORDER BY created_at DESC LIMIT 1),
            g.created_at
        ) DESC
        """,
        (uid,)
    ) or []
    return jsonify({'success': True, 'groups': groups})


@chat_bp.route('/groups', methods=['POST'])
@token_required
def create_group(current_user):
    """Admin creates a new group chat and selects members."""
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can create group chats.'}), 403

    data = request.json or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    member_ids = data.get('member_ids', [])

    if not name:
        return jsonify({'message': 'Group name is required.'}), 400
    if not member_ids:
        return jsonify({'message': 'Select at least one member.'}), 400

    group = execute_query(
        "INSERT INTO chat_groups (name, description, created_by) VALUES (%s, %s, %s) RETURNING *",
        (name, description, current_user['id']), commit=True, fetchone=True
    )
    if not group:
        return jsonify({'message': 'Failed to create group.'}), 500

    gid = group['id']
    # Add admin as member
    all_members = list(set([current_user['id']] + [int(m) for m in member_ids]))
    for uid in all_members:
        execute_query(
            "INSERT INTO chat_group_members (group_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (gid, uid), commit=True
        )

    return jsonify({'success': True, 'group': group}), 201


@chat_bp.route('/groups/<int:group_id>', methods=['GET'])
@token_required
def get_group(current_user, group_id):
    """Get group info and members."""
    # Check membership
    member = execute_query(
        "SELECT id FROM chat_group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user['id']), fetchone=True
    )
    if not member and current_user['role'] != 'admin':
        return jsonify({'message': 'Not a member of this group.'}), 403

    group = execute_query(
        "SELECT g.*, u.full_name as creator_name FROM chat_groups g JOIN users u ON g.created_by = u.id WHERE g.id = %s",
        (group_id,), fetchone=True
    )
    if not group:
        return jsonify({'message': 'Group not found.'}), 404

    members = execute_query(
        "SELECT u.id, u.full_name, u.email, u.role FROM chat_group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = %s ORDER BY u.full_name",
        (group_id,)
    ) or []

    return jsonify({'success': True, 'group': group, 'members': members})


@chat_bp.route('/groups/<int:group_id>/members', methods=['PUT'])
@token_required
def update_group_members(current_user, group_id):
    """Admin adds or removes members from a group."""
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can manage group members.'}), 403

    data = request.json or {}
    member_ids = data.get('member_ids', [])

    # Remove all current members except admin
    execute_query(
        "DELETE FROM chat_group_members WHERE group_id = %s AND user_id != %s",
        (group_id, current_user['id']), commit=True
    )
    # Re-add selected members + admin
    all_members = list(set([current_user['id']] + [int(m) for m in member_ids]))
    for uid in all_members:
        execute_query(
            "INSERT INTO chat_group_members (group_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (group_id, uid), commit=True
        )
    return jsonify({'success': True})


@chat_bp.route('/groups/<int:group_id>', methods=['DELETE'])
@token_required
def dissolve_group(current_user, group_id):
    """Admin dissolves (permanently deletes) a group."""
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can dissolve groups.'}), 403
    group = execute_query("SELECT id FROM chat_groups WHERE id = %s", (group_id,), fetchone=True)
    if not group:
        return jsonify({'message': 'Group not found.'}), 404
    # CASCADE deletes members and messages
    execute_query("DELETE FROM chat_groups WHERE id = %s", (group_id,), commit=True)
    return jsonify({'success': True})


@chat_bp.route('/groups/<int:group_id>/messages', methods=['GET'])
@token_required
def get_group_messages(current_user, group_id):
    """Fetch messages for a group (polling — returns only new messages if since= provided)."""
    member = execute_query(
        "SELECT id FROM chat_group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user['id']), fetchone=True
    )
    if not member:
        return jsonify({'message': 'Not a member of this group.'}), 403

    since = request.args.get('since')
    if since:
        msgs = execute_query(
            "SELECT m.*, u.full_name as sender_name, u.role as sender_role "
            "FROM chat_messages m JOIN users u ON m.sender_id = u.id "
            "WHERE m.group_id = %s AND m.created_at > %s::timestamp "
            "ORDER BY m.created_at ASC",
            (group_id, since)
        ) or []
    else:
        msgs = execute_query(
            "SELECT m.*, u.full_name as sender_name, u.role as sender_role "
            "FROM chat_messages m JOIN users u ON m.sender_id = u.id "
            "WHERE m.group_id = %s ORDER BY m.created_at ASC LIMIT 100",
            (group_id,)
        ) or []
    return jsonify({'success': True, 'messages': msgs})


@chat_bp.route('/groups/<int:group_id>/messages', methods=['POST'])
@token_required
def send_group_message(current_user, group_id):
    """Send a message (with optional file attachment) to a group."""
    member = execute_query(
        "SELECT id FROM chat_group_members WHERE group_id = %s AND user_id = %s",
        (group_id, current_user['id']), fetchone=True
    )
    if not member:
        return jsonify({'message': 'Not a member of this group.'}), 403

    data = request.json or {}
    text = (data.get('text') or '').strip()
    file_name = data.get('file_name')
    file_type = data.get('file_type', 'application/octet-stream')
    file_data = data.get('file_data')

    if not text and not file_data:
        return jsonify({'message': 'Message or file is required.'}), 400

    msg_text = text or f'📎 {file_name}'
    msg = execute_query(
        "INSERT INTO chat_messages (sender_id, group_id, text, file_name, file_type, file_data) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, sender_id, group_id, text, file_name, file_type, created_at",
        (current_user['id'], group_id, msg_text, file_name, file_type, file_data), commit=True, fetchone=True
    )
    return jsonify({'success': True, 'message': msg}), 201


# ─── Chat File Download ───────────────────────────────────────────────────────

@chat_bp.route('/files/<int:message_id>', methods=['GET'])
def download_chat_file(message_id):
    """Download a file attached to a chat message — no auth (ID is serial)."""
    import base64
    from flask import Response
    row = execute_query(
        "SELECT file_name, file_type, file_data FROM chat_messages WHERE id = %s AND file_data IS NOT NULL",
        (message_id,), fetchone=True
    )
    if not row:
        return jsonify({'message': 'File not found.'}), 404
    try:
        file_bytes = base64.b64decode(row['file_data'])
        return Response(
            file_bytes,
            mimetype=row['file_type'] or 'application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{row["file_name"]}"',
                'Content-Length': str(len(file_bytes))
            }
        )
    except Exception as e:
        return jsonify({'message': f'Failed to decode file: {str(e)}'}), 500
