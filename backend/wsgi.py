import sys
import traceback

def application(environ, start_response):
    start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
    return [b"CRITICAL BOOT ERROR:\n\n" + traceback.format_exc().encode()]

try:
    from app import create_app
    app = create_app()
except Exception as e:
    app = application

if __name__ == "__main__":
    app.run()
