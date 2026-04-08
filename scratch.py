import urllib.request
import urllib.error
import json

token = "PUT_YOUR_AUTH_TOKEN_HERE"

url = 'https://backend-centric-infrastructure-tick-ten.vercel.app/api/dashboard/admin/overview'
req = urllib.request.Request(url, headers={
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
})

try:
    response = urllib.request.urlopen(req)
    print("STATUS", response.status)
    print(json.dumps(json.loads(response.read().decode()), indent=2))
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    print("BODY:")
    print(e.read().decode())
except Exception as e:
    print("Other error:", e)
