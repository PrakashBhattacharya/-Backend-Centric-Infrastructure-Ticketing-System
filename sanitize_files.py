import os

files_to_sanitize = {
    'requirements.txt': """Flask==3.0.2
Werkzeug==3.0.1
Flask-CORS==4.0.0
PyJWT==2.8.0
python-dotenv==1.0.1
gunicorn==21.2.0
pg8000==1.30.5
""",
    'api/index.py': """import sys
import os
import traceback

# 1. Standardize System Path
api_dir = os.path.dirname(__file__)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

def create_emergency_app(error_msg):
    from flask import Flask, jsonify
    dummy = Flask(__name__)
    @dummy.route('/', defaults={'path': ''})
    @dummy.route('/<path:path>')
    def report_error(path):
        return jsonify({
            "status": "BOOTSTRAP_FAILURE",
            "error": error_msg
        }), 500
    return dummy

# 2. High-Observation Bootstrap
try:
    from app import create_app
    app = create_app()
except Exception:
    app = create_emergency_app(traceback.format_exc())

if __name__ == "__main__":
    app.run()
""",
    'api/app/config.py': """import os
from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..', '..'))

class Config:
    BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
    SECRET_KEY = os.environ.get('SECRET_KEY', 'infratick-enterprise-secret-2026')
    POSTGRES_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(PROJECT_ROOT, 'frontend'))
"""
}

for path, content in files_to_sanitize.items():
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        print(f"Sanitized: {path}")
