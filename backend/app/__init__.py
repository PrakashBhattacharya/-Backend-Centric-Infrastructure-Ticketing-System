import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from .config import Config
from .models import init_db
from datetime import datetime, date
import json

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles PostgreSQL datetime objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def create_app(config_class=Config):
    """
    InfraTick Application Factory.
    Standardizes app creation for both development and production.
    """
    app = Flask(__name__, static_folder=config_class.FRONTEND_DIR)
    app.config.from_object(config_class)
    
    # Modern Flask JSON handling for datetimes
    app.json_encoder = DateTimeEncoder

    # Initialize CORS with explicit settings for local dev
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize Database (Handled by WSGI or lazy loaders in cloud)
    # with app.app_context():
    #     init_db()

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.tickets import tickets_bp
    from .routes.chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(chat_bp)

    # API Health Check
    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({
            "status": "Enterprise Backend Operational",
            "environment": "Production" if not app.debug else "Development",
            "db_path": app.config['DB_PATH']
        })

    # Serve Frontend Static Files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Unified static file server for deployment."""
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            # Default to login.html for root or missing routes
            return send_from_directory(app.static_folder, 'login.html')

    return app
