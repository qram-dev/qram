#!/usr/bin/env python3
import requests

r = requests.get('http://localhost:4040/api/tunnels')
assert r.ok
j = r.json()
print(j['tunnels'][0]['public_url'])
