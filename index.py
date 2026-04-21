import sys
import os

# Ensure the backend directory is in the Python path so we can import 'app'
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from app import create_app
from app.models import init_db

try:
    app = create_app()
    # In Vercel/Cloud, we might want to skip init_db on every request
    # but for stabilization, we ensure the context is safe
    with app.app_context():
        # init_db() # Optional: Disable if still 500ing
        pass 
except Exception as e:
    import traceback
    error_info = traceback.format_exc()
    from flask import Flask
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"ROOT_CRASH:\n{error_info}", 500

# Vercel needs 'app' to be exported at the top level
if __name__ == "__main__":
    app.run()
