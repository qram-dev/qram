# Tests classification

1. **UNIT** - no filesystem/network allowed; test python code in vacuum, as precise as possible (1 test = 1 function).
2. **COMPONENT** - controllable filesystem, still no network; test python in atmosphere, still as precise as possible, but might be broader.
3. **INTEGRATION** - controllable filesystem, network is mocked; test broader use scenarios.
4. **SYSTEM** - controllable filesystem, network allowed, additional Docker setup is required; test installed application as a whole with user-like input

**ASSETS/** - directory with "pre-built binaries" for controllable filesystem

# Running tests
`$ pytest -- test/<component of interest>`.

Unit, componnt and integration tests should not require any specific configuration.


## Running system tests
System test harness consists of two parts. Both perform tests using a realworld remote repo and
API - but part `A` tests only basic API functionality, while part `B` actually publishes test server
as webhook endpoint for repo provider.

The setup goes like this:
- use [ngrok](https://ngrok.com), [webhook.site](https://webhook.site) or any of their alternatives
to provide a public URL tunnel to your `localhost:8888`
- create `.env` file with contents like these:
```bash
QRAM_APP_HMAC=super-secret-for-webhook-validation
QRAM_APP_GITHUB_APP_ID=123
QRAM_APP_GITHUB_INSTALLATION_ID=45678
QRAM_APP_GITHUB_PEM_FILE=/home/artalus/git/qram/qram-test.2023-05-08.private-key.pem
QRAM_WEBHOOK_URL=https://a1b2-c3d4-e5f6.ngrok.io
```
- run `pytest --cov -- test/system/` with `-m sys-A` to test part `A` or `-m sys-B` to test part `B`.

The `???` fixture uses Github REST API to reconfigure `webhook url` in the specified app.
Tests will then use the API to query and update a Github repo.
