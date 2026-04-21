import os
from flask import Flask, jsonify
from flask_cors import CORS
from .config import Config
from datetime import datetime, date

def create_app(config_class=Config):
    """
    InfraTick Application Factory - Flask 3.0 compatible.
    """
    app = Flask(__name__)
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

    return app
