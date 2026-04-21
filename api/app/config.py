import os
from dotenv import load_dotenv

# Backend root is one level up from this file, Project root is one level up from backend
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..', '..'))
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')

# Load .env file with absolute path
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"[Config] Successfully loaded .env from {ENV_PATH}")
else:
    load_dotenv() # Fallback to standard search
    print(f"[Config] WARNING: .env not found at {ENV_PATH}, falling back to default search.")

class Config:
    """Professional configuration with standardized paths."""
    # Backend root is one level up from this file
    BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'infratick-enterprise-secret-2026')
    
    # Database path in instance folder (Legacy SQLite)
    INSTANCE_PATH = os.path.join(BACKEND_ROOT, 'instance')
    DB_PATH = os.environ.get('DB_PATH', os.path.join(INSTANCE_PATH, 'infratick.db'))
    
    # Provide Postgres URL from Vercel env
    POSTGRES_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
    
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Frontend assets location
    FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(PROJECT_ROOT, 'frontend'))
