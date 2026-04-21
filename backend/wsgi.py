import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import init_db

try:
    app = create_app()
    with app.app_context():
        init_db()
except Exception as e:
    import traceback
    error_info = traceback.format_exc()
    from flask import Flask
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"CRITICAL_STARTUP_ERROR:\n{error_info}", 500

if __name__ == "__main__":
    app.run()
