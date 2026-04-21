import urllib.request
import urllib.error

try:
    r = urllib.request.urlopen('https://backend-centric-infrastructure-tick-ten.vercel.app/api/status')
    print(r.read().decode())
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    body = e.read().decode()
    print(body)
