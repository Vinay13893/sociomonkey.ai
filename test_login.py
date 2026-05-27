import json
import urllib.request

url = 'http://127.0.0.1:5000/api/auth/login'
data = json.dumps({'email':'admin@gangarealty.com','password':'Admin@123'}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as r:
    print(r.status)
    print(r.read().decode())
