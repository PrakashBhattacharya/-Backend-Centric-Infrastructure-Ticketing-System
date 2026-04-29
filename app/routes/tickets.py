"""
Tickets API blueprint — handles all CRUD operations and status updates.
"""

from flask import Blueprint, jsonify, request
from .auth import token_required
from ..models import (
    create_ticket, get_tickets, get_ticket_by_id,
    update_ticket_status, assign_ticket, add_comment, get_comments,
    approve_ticket, reject_ticket,
    request_sla_extension, get_sla_extension_requests,
    approve_sla_extension, reject_sla_extension,
    add_attachment, get_ticket_attachments, get_attachment_data
)

tickets_bp = Blueprint('tickets', __name__, url_prefix='/api/tickets')

@tickets_bp.route('', methods=['POST'])
@token_required
def submit_ticket(current_user):
    data = request.json or {}
    subject = data.get('subject')
    description = data.get('description', '')
    service_area = data.get('serviceArea', 'Other')
    environment = data.get('environment', 'Production')
    priority = data.get('priority', 'Medium')
    file_name = data.get('fileName')
    file_type = data.get('fileType', 'application/octet-stream')
    file_data = data.get('fileData')

    if not subject:
        return jsonify({'success': False, 'message': 'Subject is required'}), 400

    ticket = create_ticket(subject, description, service_area, environment, priority, current_user['id'])
    if not ticket:
        return jsonify({'success': False, 'message': 'Failed to create ticket'}), 500

    if file_name and file_data:
        try:
            add_attachment(ticket['id'], current_user['id'], file_name, file_type, file_data)
        except Exception as e:
            print(f"[ATTACHMENT] Failed to save attachment: {e}")

    return jsonify({'success': True, 'ticket': ticket}), 201

@tickets_bp.route('/my', methods=['GET'])
@token_required
def get_my_tickets(current_user):
    tickets = get_tickets(filters={'created_by': current_user['id']})
    return jsonify({'success': True, 'tickets': tickets})

@tickets_bp.route('', methods=['GET'])
@token_required
def get_all_tickets(current_user):
    if current_user['role'] not in ['engineer', 'admin']:
        return jsonify({'message': 'Unauthorized'}), 403
    tickets = get_tickets()
    return jsonify({'success': True, 'tickets': tickets})

@tickets_bp.route('/<int:ticket_id>', methods=['GET'])
@token_required
def get_ticket(current_user, ticket_id):
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404
    
    if current_user['role'] == 'member' and ticket['created_by'] != current_user['id']:
        return jsonify({'message': 'Unauthorized'}), 403
        
    comments = get_comments(ticket_id)
    attachments = get_ticket_attachments(ticket_id)
    return jsonify({'success': True, 'ticket': ticket, 'comments': comments, 'attachments': attachments})

@tickets_bp.route('/<int:ticket_id>/status', methods=['PUT'])
@token_required
def update_status(current_user, ticket_id):
    data = request.json
    new_status = data.get('status')

    ticket = get_ticket_by_id(ticket_id)
    if not ticket: return jsonify({'message': 'Not found'}), 404

    # Engineers can only submit for approval (not directly resolve)
    if current_user['role'] == 'engineer' and new_status == 'Resolved':
        return jsonify({'success': False, 'message': 'Engineers must submit for admin approval first.'}), 403

    # Only admins can directly set Resolved or Closed
    if new_status in ('Resolved', 'Closed') and current_user['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Only admins can mark tickets as Resolved or Closed.'}), 403

    update_ticket_status(ticket_id, new_status, current_user['id'])
    return jsonify({'success': True})

@tickets_bp.route('/<int:ticket_id>/approve', methods=['PUT'])
@token_required
def approve(current_user, ticket_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can approve resolutions.'}), 403
    success = approve_ticket(ticket_id, current_user['id'])
    if not success:
        return jsonify({'message': 'Ticket not found or not pending approval.'}), 400
    return jsonify({'success': True})

@tickets_bp.route('/<int:ticket_id>/reject', methods=['PUT'])
@token_required
def reject(current_user, ticket_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can reject resolutions.'}), 403
    data = request.json or {}
    reason = data.get('reason', '')
    success = reject_ticket(ticket_id, current_user['id'], reason)
    if not success:
        return jsonify({'message': 'Ticket not found or not pending approval.'}), 400
    return jsonify({'success': True})

@tickets_bp.route('/<int:ticket_id>/assign', methods=['PUT'])
@token_required
def assign(current_user, ticket_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can assign tickets'}), 403
    
    data = request.json
    engineer_id = data.get('engineer_id')
    
    if not engineer_id:
        return jsonify({'message': 'Engineer ID is required'}), 400
        
    try:
        engineer_id = int(engineer_id)
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid Engineer ID format'}), 400

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404
    if ticket['status'] in ('Resolved', 'Closed'):
        return jsonify({'message': 'Cannot reassign a resolved or closed ticket.'}), 400

    success = assign_ticket(ticket_id, engineer_id, current_user['id'])
    if not success:
        return jsonify({'message': 'User not found or not an engineer'}), 404
    return jsonify({'success': True})

@tickets_bp.route('/<int:ticket_id>/comments', methods=['POST'])
@token_required
def post_comment(current_user, ticket_id):
    data = request.json
    text = data.get('text')
    if not text: return jsonify({'success': False}), 400
    
    add_comment(ticket_id, current_user['id'], text)
    return jsonify({'success': True})

# ─── Attachment Endpoints ─────────────────────────────────────────────────────

@tickets_bp.route('/<int:ticket_id>/attachments', methods=['POST'])
@token_required
def upload_attachment(current_user, ticket_id):
    """Engineer attaches a file when submitting for approval."""
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404
    
    # Only assigned engineer or ticket creator can attach files
    if current_user['role'] == 'engineer' and ticket.get('assigned_to') != current_user['id']:
        return jsonify({'message': 'You can only attach files to tickets assigned to you.'}), 403
    if current_user['role'] == 'member' and ticket.get('created_by') != current_user['id']:
        return jsonify({'message': 'You can only attach files to your own tickets.'}), 403

    data = request.json or {}
    file_name = data.get('fileName')
    file_type = data.get('fileType', 'application/octet-stream')
    file_data = data.get('fileData')

    if not file_name or not file_data:
        return jsonify({'message': 'File name and data are required.'}), 400

    try:
        add_attachment(ticket_id, current_user['id'], file_name, file_type, file_data)
        return jsonify({'success': True}), 201
    except Exception as e:
        print(f"[ATTACHMENT] Error: {e}")
        return jsonify({'message': 'Failed to save attachment.'}), 500

@tickets_bp.route('/attachments/<int:attachment_id>', methods=['GET'])
@token_required
def download_attachment(current_user, attachment_id):
    """Download an attachment (returns base64 data for client-side decoding)."""
    attachment = get_attachment_data(attachment_id)
    if not attachment:
        return jsonify({'message': 'Attachment not found.'}), 404
    return jsonify({'success': True, 'attachment': attachment})

# ─── SLA Extension Endpoints ─────────────────────────────────────────────────

@tickets_bp.route('/<int:ticket_id>/sla-extension', methods=['POST'])
@token_required
def request_extension(current_user, ticket_id):
    """Engineer requests an SLA extension for a ticket assigned to them."""
    if current_user['role'] != 'engineer':
        return jsonify({'message': 'Only engineers can request SLA extensions.'}), 403
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found.'}), 404
    if ticket.get('assigned_to') != current_user['id']:
        return jsonify({'message': 'You can only request extensions for tickets assigned to you.'}), 403
    if ticket['status'] not in ('In Progress', 'Open'):
        return jsonify({'message': 'Extensions can only be requested for active tickets.'}), 400

    # Block if SLA is already breached
    from datetime import datetime
    try:
        deadline = datetime.strptime(ticket['sla_deadline'], '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() > deadline:
            return jsonify({'message': 'SLA has already been breached. Extensions cannot be requested after the deadline has passed.'}), 400
    except Exception:
        pass

    data = request.json or {}
    requested_hours = data.get('requested_hours')
    reason = data.get('reason', '').strip()

    if not requested_hours or float(requested_hours) <= 0:
        return jsonify({'message': 'Requested hours must be a positive number.'}), 400
    if not reason:
        return jsonify({'message': 'A reason is required.'}), 400

    row, err = request_sla_extension(ticket_id, current_user['id'], float(requested_hours), reason)
    if err:
        return jsonify({'success': False, 'message': err}), 409
    return jsonify({'success': True, 'request': row}), 201

@tickets_bp.route('/sla-extensions', methods=['GET'])
@token_required
def list_extensions(current_user):
    """Admin: list all SLA extension requests. Engineer: list their own."""
    if current_user['role'] == 'admin':
        status_filter = request.args.get('status')
        requests = get_sla_extension_requests(status=status_filter)
    elif current_user['role'] == 'engineer':
        # Return requests for tickets assigned to this engineer
        from ..models import execute_query
        requests = execute_query(
            "SELECT r.*, u.full_name as engineer_name, t.subject as ticket_subject, "
            "t.sla_deadline, t.priority "
            "FROM sla_extension_requests r "
            "JOIN users u ON r.engineer_id = u.id "
            "JOIN tickets t ON r.ticket_id = t.id "
            "WHERE r.engineer_id = %s ORDER BY r.created_at DESC",
            (current_user['id'],)
        ) or []
    else:
        return jsonify({'message': 'Unauthorized'}), 403
    return jsonify({'success': True, 'requests': requests})

@tickets_bp.route('/sla-extensions/<int:request_id>/approve', methods=['PUT'])
@token_required
def approve_extension(current_user, request_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can approve SLA extensions.'}), 403
    data = request.json or {}
    note = data.get('note', '')
    ok, err = approve_sla_extension(request_id, current_user['id'], note)
    if not ok:
        return jsonify({'message': err}), 400
    return jsonify({'success': True})

@tickets_bp.route('/sla-extensions/<int:request_id>/reject', methods=['PUT'])
@token_required
def reject_extension(current_user, request_id):
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Only admins can reject SLA extensions.'}), 403
    data = request.json or {}
    note = data.get('note', '')
    ok, err = reject_sla_extension(request_id, current_user['id'], note)
    if not ok:
        return jsonify({'message': err}), 400
    return jsonify({'success': True})
