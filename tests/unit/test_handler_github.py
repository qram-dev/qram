import hashlib
import hmac
import json
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from qram.config import AppConfig, CfgGithub
from qram.web.github import GithubWebhookHandler
from qram.web.github.handler import InvalidPayloadError


@pytest.fixture
def cfg() -> AppConfig:
    return AppConfig.model_construct(
        cors_origin='',
        github=CfgGithub.model_construct(hmac='secret'),
    )


@pytest.fixture
def handler(cfg: AppConfig) -> GithubWebhookHandler:
    return GithubWebhookHandler(cfg)


class TestVerifySignature:
    def test_valid_signature_allows_request(self, handler: GithubWebhookHandler) -> None:
        body = b'content'
        secret = handler.github_config.hmac.encode()
        mac = hmac.new(secret, body, hashlib.sha256).hexdigest()

        req = Mock(spec=Request)
        req.headers = {'x-hub-signature-256': f'sha256={mac}'}

        resp = handler.verify_signature(req, body)
        assert resp is None

    def test_missing_signature_header_fails(self, handler: GithubWebhookHandler) -> None:
        req = Mock(spec=Request)
        req.headers = {}

        resp = handler.verify_signature(req, b'body')
        assert resp
        assert resp.status_code == 401
        assert 'missing' in error_body(resp)

    def test_malformed_signature_fails(self, handler: GithubWebhookHandler) -> None:
        req = Mock(spec=Request)
        req.headers = {'x-hub-signature-256': 'malformed'}

        resp = handler.verify_signature(req, b'body')
        assert resp
        assert resp.status_code == 401
        assert 'malformed' in error_body(resp)

    def test_non_sha256_signature_fails(self, handler: GithubWebhookHandler) -> None:
        req = Mock(spec=Request)
        req.headers = {'x-hub-signature-256': 'sha1=abcdef'}

        resp = handler.verify_signature(req, b'body')
        assert resp
        assert resp.status_code == 401
        assert 'unsupported' in error_body(resp)

    def test_signature_not_matching_body_fails(self, handler: GithubWebhookHandler) -> None:
        body = b'content'
        secret = handler.github_config.hmac.encode()
        mac = hmac.new(secret, body, hashlib.sha256).hexdigest()

        # Tamper with body
        tampered_body = b'{onten}'

        req = Mock(spec=Request)
        req.headers = {'x-hub-signature-256': f'sha256={mac}'}

        resp = handler.verify_signature(req, tampered_body)
        assert resp
        assert resp.status_code == 401
        assert 'does not match' in error_body(resp)


class TestVerifyJsonPayload:
    async def test_valid_json_payload(self, handler: GithubWebhookHandler) -> None:
        req = Mock(spec=Request)
        req.json = AsyncMock(return_value={'key': 'value'})

        payload = await handler.verify_json_payload(req)
        assert payload == {'key': 'value'}

    class TestInvalidPayloads:
        async def test_invalid_json(self, handler: GithubWebhookHandler) -> None:
            req = Mock(spec=Request)
            req.json = AsyncMock(side_effect=ValueError('{"invalid json'))

            with pytest.raises(InvalidPayloadError, match='failed to parse'):
                _ = await handler.verify_json_payload(req)

        async def test_empty_payload(self, handler: GithubWebhookHandler) -> None:
            req = Mock(spec=Request)
            req.json = AsyncMock(return_value={})

            with pytest.raises(InvalidPayloadError, match='empty payload'):
                _ = await handler.verify_json_payload(req)

        async def test_non_dict_json(self, handler: GithubWebhookHandler) -> None:
            req = Mock(spec=Request)
            req.json = AsyncMock(return_value='1234')

            with pytest.raises(InvalidPayloadError, match='not a dict'):
                _ = await handler.verify_json_payload(req)

        async def test_dict_with_non_string_keys(self, handler: GithubWebhookHandler) -> None:
            req = Mock(spec=Request)
            req.json = AsyncMock(return_value={1: 'value'})

            with pytest.raises(InvalidPayloadError, match='not all strings'):
                _ = await handler.verify_json_payload(req)


def error_body(resp: JSONResponse) -> str:
    j: dict[str, str] = json.loads(bytes(resp.body).decode())
    assert isinstance(j, dict)
    return str(j['error'])
