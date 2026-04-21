import sys
import os

# 1. Standardize Python Path for Vercel
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from app import create_app
from app.models import init_db

def bootstrap():
    """Helper to initialize the app instance."""
    try:
        return create_app()
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        from flask import Flask
        dummy = Flask(__name__)
        @dummy.route('/', defaults={'path': ''})
        @dummy.route('/<path:path>')
        def catch_all(path):
            return f"CRITICAL_APP_STARTUP_FAILURE:\n{error_info}", 500
        return dummy

# Vercel MUST see this variable at the top level
app = bootstrap()

# 2. Safe Database Boot (Deferred to first request)
@app.before_request
def ensure_connected():
    if not hasattr(app, '_db_primed'):
        try:
            from flask import current_app
            with current_app.app_context():
                init_db()
            app._db_primed = True
        except Exception as e:
            print(f"[BOOT] Database priming deferred: {e}")

if __name__ == "__main__":
    app.run()
