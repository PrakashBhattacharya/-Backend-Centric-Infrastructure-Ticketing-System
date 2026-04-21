import sys
import os
import traceback

# Root directory (one level up from api/)
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

def create_emergency_app(error_msg):
    from flask import Flask, jsonify
    dummy = Flask(__name__)
    @dummy.route('/', defaults={'path': ''})
    @dummy.route('/<path:path>')
    def report_error(path):
        return jsonify({"status": "BOOT_FAILURE", "error": error_msg}), 500
    return dummy

try:
    from app import create_app
    app = create_app()
except Exception:
    app = create_emergency_app(traceback.format_exc())

if __name__ == "__main__":
    app.run()
