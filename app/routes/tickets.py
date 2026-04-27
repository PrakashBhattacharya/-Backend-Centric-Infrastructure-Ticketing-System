"""
Tickets API blueprint — handles all CRUD operations and status updates.
"""

from flask import Blueprint, jsonify, request
from .auth import token_required
from ..models import (
    create_ticket, get_tickets, get_ticket_by_id,
    update_ticket_status, assign_ticket, add_comment, get_comments,
    approve_ticket, reject_ticket
)

tickets_bp = Blueprint('tickets', __name__, url_prefix='/api/tickets')

@tickets_bp.route('', methods=['POST'])
@token_required
def submit_ticket(current_user):
    data = request.json
    subject = data.get('subject')
    description = data.get('description', '')
    service_area = data.get('serviceArea', 'Other')
    environment = data.get('environment', 'Production')
    priority = data.get('priority', 'Medium')

    if not subject:
        return jsonify({'success': False, 'message': 'Subject is required'}), 400

    ticket = create_ticket(subject, description, service_area, environment, priority, current_user['id'])
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
    
    # Simple ACL: members can only see their own tickets
    if current_user['role'] == 'member' and ticket['created_by'] != current_user['id']:
        return jsonify({'message': 'Unauthorized'}), 403
        
    comments = get_comments(ticket_id)
    return jsonify({'success': True, 'ticket': ticket, 'comments': comments})

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
