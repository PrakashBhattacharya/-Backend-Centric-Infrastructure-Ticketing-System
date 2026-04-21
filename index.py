import sys
import os

# 1. Standardize Python Path for Vercel
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from app import create_app
from app.models import init_db

# 2. Main High-Stability Initialization
try:
    # Use standard factory
    app = create_app()
    
    # 3. Safe Database Boot
    # We call init_db with a safety wrapper to avoid the "Cold Start Crash"
    @app.before_request
    def ensure_connected():
        if not hasattr(app, '_db_primed'):
            try:
                with app.app_context():
                    init_db()
                app._db_primed = True
            except Exception as e:
                print(f"[BOOT] Database priming deferred: {e}")

except Exception as e:
    # 4. Emergency Diagnostic Fallback
    # If the main app fails to even START, we show the exact Python traceback
    # instead of a generic Vercel 500 error.
    import traceback
    error_info = traceback.format_exc()
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"CRITICAL_APP_STARTUP_FAILURE:\n{error_info}", 500

# Vercel looks for 'app' to export as the handler
if __name__ == "__main__":
    app.run()
