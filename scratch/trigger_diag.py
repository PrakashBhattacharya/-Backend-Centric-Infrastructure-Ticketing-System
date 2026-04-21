import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app import create_app
from app.models import get_admin_stats

app = create_app()
with app.app_context():
    print("Executing get_admin_stats()...")
    stats = get_admin_stats()
    print("\nResult check:")
    print(f"Total Open: {stats.get('total_open')}")
    print(f"Engineers Count: {len(stats.get('engineers', []))}")
    
    # Also check if debug log has been written
    log_path = os.path.join(os.getcwd(), 'debug-c9a78c.log')
    if os.path.exists(log_path):
        print("\n--- DEBUG LOG CONTENT ---")
        with open(log_path, 'r') as f:
            print(f.read())
    else:
        print("\nNo debug log found at root.")
