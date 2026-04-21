import sys
import os

# Ensure the project root is on the path so `app` package can be found
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# app must be defined at module level for Vercel's static analysis
app = None

try:
    from app import create_app
    app = create_app()
except Exception as e:
    import traceback
    _boot_error = traceback.format_exc()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def report_error(path):
        return jsonify({"status": "BOOT_FAILURE", "error": _boot_error}), 500

# Vercel requires the WSGI callable to be named `app`, `application`, or `handler`
# `app` is already set above — this satisfies the static check
application = app

if __name__ == "__main__":
    app.run()
