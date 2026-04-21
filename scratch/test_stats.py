import os
import sys
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app import create_app
from app.models import get_admin_stats

app = create_app()
with app.app_context():
    try:
        stats = get_admin_stats()
        print("Successfully fetched stats:")
        for key in ['total_open', 'breaches_today', 'mttr', 'avg_aging', 'backlogTrendData', 'regionLoadData']:
            print(f"{key}: {stats.get(key)}")
    except Exception as e:
        print(f"Error fetching stats: {e}")
        import traceback
        traceback.print_exc()
