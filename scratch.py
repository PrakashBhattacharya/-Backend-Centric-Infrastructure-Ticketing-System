import urllib.request
import urllib.error
import json

# First, login to get a token
login_url = 'https://backend-centric-infrastructure-tick-ten.vercel.app/api/login'
login_data = json.dumps({'email': 'manik102@gmail.com', 'password': '123456'}).encode()
login_req = urllib.request.Request(login_url, data=login_data, headers={'Content-Type': 'application/json'})

try:
    login_resp = urllib.request.urlopen(login_req)
    login_json = json.loads(login_resp.read().decode())
    token = login_json['token']
    print("Login successful, got token")
    
    # Now fetch a ticket detail
    ticket_url = 'https://backend-centric-infrastructure-tick-ten.vercel.app/api/tickets/15'
    ticket_req = urllib.request.Request(ticket_url, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    })
    ticket_resp = urllib.request.urlopen(ticket_req)
    ticket_json = json.loads(ticket_resp.read().decode())
    
    t = ticket_json['ticket']
    print(f"\nTicket #{t['id']}:")
    print(f"  sla_deadline: {repr(t['sla_deadline'])}")
    print(f"  created_at:   {repr(t['created_at'])}")
    print(f"  updated_at:   {repr(t['updated_at'])}")
    
except urllib.error.HTTPError as e:
    print(f"HTTP error: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
