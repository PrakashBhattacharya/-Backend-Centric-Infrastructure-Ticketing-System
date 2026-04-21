import os
from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..', '..'))

class Config:
    BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
    SECRET_KEY = os.environ.get('SECRET_KEY', 'infratick-enterprise-secret-2026')
    POSTGRES_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(PROJECT_ROOT, 'frontend'))
