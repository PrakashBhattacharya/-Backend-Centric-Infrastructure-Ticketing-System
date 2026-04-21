import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import init_db

app = create_app()

# Initialize database schema on startup (creates tables if missing)
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run()
