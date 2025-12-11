import httpx

r = httpx.post('https://webhook.site/token', timeout=10)
assert r.is_success
print(r.json()['uuid'], end='')
