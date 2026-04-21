import sys
import os

# 1. Standardize Python Path for Vercel
# Ensure the 'backend/app' module can be imported
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from app import create_app
from app.models import init_db

def bootstrap():
    """High-stability factory to initialize the real app."""
    try:
        instance = create_app()
        # High-Stability: Ensure DB schema is ready
        with instance.app_context():
            init_db()
        return instance
    except Exception as e:
        # Emergency Diagnostic Fallback
        import traceback
        error_info = traceback.format_exc()
        from flask import Flask, jsonify
        dummy = Flask(__name__)
        @dummy.route('/', defaults={'path': ''})
        @dummy.route('/<path:path>')
        def catch_all(path):
            return f"FINAL_BOOT_CRASH:\n{error_info}", 500
        return dummy

# Vercel's 'app' export
app = bootstrap()

if __name__ == "__main__":
    app.run()
