import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    """Professional configuration with standardized paths."""
    # Backend root is one level up from this file
    BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'infratick-enterprise-secret-2026')
    
    # Database path in instance folder
    INSTANCE_PATH = os.path.join(BACKEND_ROOT, 'instance')
    DB_PATH = os.environ.get('DB_PATH', os.path.join(INSTANCE_PATH, 'infratick.db'))
    
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Frontend assets location
    FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(PROJECT_ROOT, 'frontend'))
