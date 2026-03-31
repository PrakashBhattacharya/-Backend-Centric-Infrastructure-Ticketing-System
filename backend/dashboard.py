from flask import Blueprint, jsonify

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/api/member/dashboard', methods=['GET'])
def member_dashboard():
    return jsonify({
        "success": True,
        "velocityData": {
            "urgent": [2, 1, 0, 4, 1, 3, 2],
            "standard": [5, 6, 4, 8, 7, 5, 9]
        },
        "priorityData": [4, 12, 24, 8],
        "backlogData": [40, 35, 38, 30, 25, 28, 22, 18],
        "slaData": [85, 10, 5]
    })

@dashboard_bp.route('/api/engineer/queue', methods=['GET'])
def engineer_queue():
    return jsonify({
        "success": True,
        "resolvedData": [15, 8, 12, 6, 9],
        "mttrData": [1.2, 1.5, 1.1, 1.8, 1.4, 2.0, 1.3],
        "telemetryData": [45, 78, 32],
        "resolvedTickets": [
            {"id": "901", "title": "Database Optimization", "time": "10h ago", "status": "Resolved"},
            {"id": "892", "title": "Switch Reset", "time": "1d ago", "status": "Resolved"},
            {"id": "885", "title": "Firewall Rules Update", "time": "2d ago", "status": "Resolved"}
        ]
    })

@dashboard_bp.route('/api/admin/overview', methods=['GET'])
def admin_overview():
    return jsonify({
        "success": True,
        "slaComplianceData": [82, 15, 3],
        "agingData": [45, 20, 10, 5],
        "backlogTrendData": [150, 140, 160, 130, 110, 90],
        "serviceImpactData": [35, 25, 15, 10, 5],
        "regionLoadData": [40, 30, 20, 10],
        "engineers": [
            { "name": "Sarah Jenkins", "assigned": 14, "resolved": 56, "mttr": "1.2h", "sla": 98, "reopens": "0.5%", "status": "excellent" },
            { "name": "Marcus Cole", "assigned": 18, "resolved": 42, "mttr": "1.8h", "sla": 94, "reopens": "1.2%", "status": "good" },
            { "name": "Elena Rostova", "assigned": 22, "resolved": 38, "mttr": "2.5h", "sla": 88, "reopens": "3.4%", "status": "warning" },
            { "name": "David Chen", "assigned": 9, "resolved": 15, "mttr": "4.2h", "sla": 75, "reopens": "5.1%", "status": "critical" },
            { "name": "Aisha Patel", "assigned": 11, "resolved": 51, "mttr": "0.9h", "sla": 99, "reopens": "0.2%", "status": "excellent" }
        ],
        "auditLogs": [
            { "icon": "fa-shield-alt", "color": "#3b82f6", "text": "Global IAM Role Policy Updated", "time": "2m ago", "danger": False },
            { "icon": "fa-user-times", "color": "#94a3b8", "text": "Offboarded Engineer ID #4092", "time": "14m ago", "danger": False },
            { "icon": "fa-exclamation-triangle", "color": "#ef4444", "text": "Login Failure Spike Detected — IP Segment A", "time": "1h ago", "danger": True },
            { "icon": "fa-database", "color": "#f59e0b", "text": "Production DB Snapshot Triggered Manually", "time": "3h ago", "danger": False },
            { "icon": "fa-key", "color": "#10b981", "text": "SSH Jump Box Certificate Auto-Rotated", "time": "5h ago", "danger": False },
            { "icon": "fa-lock-open", "color": "#8b5cf6", "text": "Sudo Privileges Escalated → Marcus Cole", "time": "6h ago", "danger": False }
        ]
    })
