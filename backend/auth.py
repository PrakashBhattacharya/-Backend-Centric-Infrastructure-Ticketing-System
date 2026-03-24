from flask import Blueprint, jsonify, request

auth_bp = Blueprint('auth', __name__)

# In-memory user store
# Pre-populated with an admin to allow easy testing
users = {
    "admin@infratick.com": {
        "fullName": "System Admin",
        "password": "password123",
        "role": "admin"
    }
}

@auth_bp.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    if not data or not all(k in data for k in ("fullName", "email", "password", "role")):
        return jsonify({"success": False, "message": "Missing required fields."}), 400
    
    email = data["email"]
    if email in users:
        return jsonify({"success": False, "message": "Email already in use."}), 409
        
    users[email] = {
        "fullName": data["fullName"],
        "password": data["password"],
        "role": data["role"].lower()
    }
    return jsonify({"success": True, "message": "Signup successful."})

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data or not all(k in data for k in ("email", "password")):
        return jsonify({"success": False, "message": "Missing credentials."}), 400
        
    email = data["email"]
    password = data["password"]
    
    user = users.get(email)
    if not user or user["password"] != password:
        return jsonify({"success": False, "message": "Invalid email or password."}), 401
    
    # In a real app we'd verify the role against the requested one, but here we just return it
    return jsonify({
        "success": True, 
        "message": "Login successful.", 
        "role": user["role"],
        "token": f"mock-jwt-token-for-{email}"
    })
