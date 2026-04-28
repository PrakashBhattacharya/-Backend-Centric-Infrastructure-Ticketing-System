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
                # Create SLA extension requests table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sla_extension_requests (
                        id SERIAL PRIMARY KEY,
                        ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                        engineer_id INTEGER NOT NULL REFERENCES users(id),
                        requested_hours NUMERIC(6,1) NOT NULL,
                        reason TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'Pending'
                            CHECK(status IN ('Pending', 'Approved', 'Rejected')),
                        admin_note TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP
                    );
                """)
                # Add rejection_note column to tickets if missing
                cursor.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS rejection_note TEXT NOT NULL DEFAULT '';")
                # Create chat tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_groups (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        created_by INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';")
                cursor.execute("ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_group_members (
                        id SERIAL PRIMARY KEY,
                        group_id INTEGER NOT NULL REFERENCES chat_groups(id) ON DELETE CASCADE,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(group_id, user_id)
                    );
                """)
                cursor.execute("ALTER TABLE chat_group_members ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        sender_id INTEGER NOT NULL REFERENCES users(id),
                        group_id INTEGER REFERENCES chat_groups(id) ON DELETE CASCADE,
                        recipient_id INTEGER REFERENCES users(id),
                        text TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES chat_groups(id) ON DELETE CASCADE;")
                cursor.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS recipient_id INTEGER REFERENCES users(id);")
                cursor.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;")
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[STARTUP MIGRATION] {e}")
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
            "environment": "Production" if not app.debug else "Development"
        })

    return app
