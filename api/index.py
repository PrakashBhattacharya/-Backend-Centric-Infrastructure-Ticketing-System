import sys
import os
import traceback

# 1. Standardize System Path
# We ensure the 'api' directory is the first place Python looks for packages.
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
            "error": error_msg,
            "path": api_dir,
            "cwd": os.getcwd(),
            "ls_api": os.listdir(api_dir) if os.path.exists(api_dir) else []
        }), 500
    return dummy

# 2. High-Observation Bootstrap
try:
    # Attempt to import the real app from the 'api/app' folder
    from app import create_app
    app = create_app()
except Exception:
    # Capture the full traceback
    error_info = traceback.format_exc()
    app = create_emergency_app(error_info)

if __name__ == "__main__":
    app.run()
