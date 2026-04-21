import sys
import os

# Link to the local app package inside the api/ folder
# In Vercel, the 'api' directory is added to sys.path automatically,
# so 'from app import create_app' will find 'api/app/__init__.py'

from app import create_app
from app.models import init_db

# Vercel looks for 'app' in api/index.py
app = create_app()

# Initialize DB on first load (Deferred logic)
@app.before_request
def startup():
    if not hasattr(app, '_db_primed'):
        try:
            with app.app_context():
                init_db()
            app._db_primed = True
        except Exception as e:
            print(f"Startup DB Error: {e}")

if __name__ == "__main__":
    app.run()
