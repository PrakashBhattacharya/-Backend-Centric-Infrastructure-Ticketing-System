import sys
import os

# Link to the backend source code
# Since this file is in api/index.py, the backend folder is one level up
parent_dir = os.path.dirname(os.path.dirname(__file__))
backend_path = os.path.join(parent_dir, 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from app import create_app
from app.models import init_db

# Vercel looks for 'app' in api/index.py automatically
app = create_app()

# Initialize DB on first load
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Deferred DB Error: {e}")

if __name__ == "__main__":
    app.run()
