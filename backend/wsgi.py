import traceback
from flask import Flask

try:
    from app import create_app
    app = create_app()
except Exception as e:
    err_msg = traceback.format_exc()
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def error_handler(path):
        return f"CRITICAL BOOT ERROR:\n\n{err_msg}", 500

if __name__ == "__main__":
    app.run()
