import urllib.request
import urllib.error
import json
import os

# Configuration from scratch.py / env context
API_BASE = 'http://127.0.0.1:5000'
LOGIN_DATA = {'email': 'manik102@gmail.com', 'password': '123456'}

def run_diag():
    print(f"Targeting Local API: {API_BASE}")
    
    # 1. Login to get token
    try:
        login_req = urllib.request.Request(
            f"{API_BASE}/api/login",
            data=json.dumps(LOGIN_DATA).encode(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(login_req) as resp:
            data = json.loads(resp.read().decode())
            token = data['token']
            print("Login successful.")
            
        # 2. Call Diagnostic Endpoint
        diag_req = urllib.request.Request(
            f"{API_BASE}/api/dashboard/admin/diag",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
        )
        with urllib.request.urlopen(diag_req) as resp:
            diag_results = json.loads(resp.read().decode())
            print("\n--- DIAGNOSTIC RESULTS ---")
            print(json.dumps(diag_results, indent=2))
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"Connection Failed: {e}")
        print("Tip: Make sure the Flask app is running at http://127.0.0.1:5000")

if __name__ == "__main__":
    run_diag()
