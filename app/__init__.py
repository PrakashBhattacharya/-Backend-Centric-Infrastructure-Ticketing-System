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

    # Run DB migrations on startup (idempotent — safe to run every cold start)
    with app.app_context():
        try:
            from .models import get_db
            conn = get_db()
            if conn:
                cursor = conn.cursor()
                # Add resolved_at column if missing
                cursor.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;")
                # Drop any existing status check constraint and re-add with Pending Approval
                cursor.execute("""
                    SELECT conname FROM pg_constraint
                    WHERE conrelid = 'tickets'::regclass
                    AND contype = 'c'
                    AND pg_get_constraintdef(oid) LIKE '%status%'
                """)
                rows = cursor.fetchall()
                for row in rows:
                    cursor.execute(f'ALTER TABLE tickets DROP CONSTRAINT IF EXISTS "{row[0]}"')
                cursor.execute(
                    "ALTER TABLE tickets ADD CONSTRAINT tickets_status_check "
                    "CHECK(status IN ('Open', 'In Progress', 'Pending Approval', 'Resolved', 'Closed'))"
                )
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[STARTUP MIGRATION] {e}")
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
