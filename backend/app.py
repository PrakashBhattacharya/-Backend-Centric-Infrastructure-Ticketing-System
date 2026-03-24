import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from auth import auth_bp

app = Flask(__name__)
# Enable CORS for all routes (important for prototype since frontend runs on different port)
CORS(app)

# Register the authentication blueprint
app.register_blueprint(auth_bp)

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "Backend is running!"})

if __name__ == '__main__':
    # Run the server on port 5000
    app.run(debug=True, host='0.0.0.0', port=5000)
