from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from qram.config import AppConfig, CfgGithub
from qram.web.app import create_app


@pytest.fixture(scope='module')
def config() -> AppConfig:
    return AppConfig(
        bind_to='127.0.0.1',
        port=8080,
        cors_origin='some-origin',
        github=CfgGithub(
            app_id='1',
            installation_id='2',
            pem='pem',
            hmac='hmac',
        ),
    )


@pytest.fixture(scope='module')
def running_app(config: AppConfig) -> TestClient:
    app = create_app(config)
    return TestClient(app)


class TestAppWithGithubHandler:
    def test_webhook_cors_headers_should_match_between_methods(
        self, config: AppConfig, running_app: TestClient
    ) -> None:
        response_options = running_app.options('/webhook')
        assert response_options.status_code == 200
        with (
            # avoid payload verification and processing
            patch('qram.web.github.handler.GithubWebhookHandler.verify_signature') as mock_verify,
            patch('qram.web.github.handler.GithubWebhookHandler.process_payload') as _mock_process,
        ):
            mock_verify.return_value = None
            response_post = running_app.post('/webhook', json={'a': 'b'})
            assert response_post.status_code == 200

        def cors_headers(r: httpx.Response) -> dict[str, str]:
            return {k: v for k, v in r.headers.items() if k.startswith('access-control-allow-')}

        assert cors_headers(response_options) == cors_headers(response_post)
        assert cors_headers(response_post)['access-control-allow-origin'] == config.cors_origin

    def test_webhook_rejects_invalid_signature(self, running_app: TestClient) -> None:
        response = running_app.post(
            '/webhook',
            json={'a': 'b'},
            headers={'x-hub-signature-256': 'sha256=whatever'},
        )
        assert response.status_code == 401
        assert 'does not match' in response.text

    def test_webhook_rejects_invalid_payload(self, running_app: TestClient) -> None:
        with patch('qram.web.github.handler.GithubWebhookHandler.verify_signature') as mock_verify:
            mock_verify.return_value = None
            response = running_app.post('/webhook', json='not-a-dict')
            assert response.status_code == 400
            assert 'not a dict' in response.text
