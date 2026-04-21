import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from .config import Config
from datetime import datetime, date

def create_app(config_class=Config):
    """
    InfraTick Application Factory - Flask 3.0 compatible.
    """
    app = Flask(__name__, static_folder=config_class.FRONTEND_DIR)
    app.config.from_object(config_class)

    # Flask 3.0+: Use json_provider_class instead of deprecated json_encoder
    from flask.json.provider import DefaultJSONProvider
    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return super().default(obj)
    app.json_provider_class = CustomJSONProvider
    app.json = CustomJSONProvider(app)

    # Initialize CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.tickets import tickets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)

    # API Health Check
    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({
            "status": "Enterprise Backend Operational",
            "environment": "Production" if not app.debug else "Development"
        })

    # Serve Frontend Static Files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Unified static file server for deployment."""
        if path and app.static_folder and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        elif app.static_folder and os.path.exists(os.path.join(app.static_folder, 'login.html')):
            return send_from_directory(app.static_folder, 'login.html')
        else:
            return jsonify({"status": "InfraTick API Running", "frontend": "not found"}), 200

    return app
