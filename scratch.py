import urllib.request
import urllib.error

url = 'https://backend-centric-infrastructure-ticketing-system-8aqixx5hn.vercel.app/api/status'
try:
    response = urllib.request.urlopen(url)
    print("STATUS", response.status)
    print(response.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    print("HEADERS:")
    print(e.headers)
    print("BODY:")
    print(e.read().decode())
except Exception as e:
    print("Other error:", e)
