import hashlib
import hmac
import logging
from typing import Any, cast, override

from fastapi import Request
from fastapi.responses import JSONResponse

from qram.config import AppConfig, CfgGithub
from qram.web import WebhookHandlerBase, get_cors_headers

logger = logging.getLogger(__name__)


class InvalidPayloadError(Exception):
    pass


class GithubWebhookHandler(WebhookHandlerBase):
    app_config: AppConfig

    def __init__(self, cfg: AppConfig) -> None:
        assert cfg.github, 'github config must be set'
        self.app_config = cfg

    @property
    def github_config(self) -> CfgGithub:
        assert self.app_config.github, 'github config must be set'
        return self.app_config.github

    @override
    def get_cors_headers(self) -> dict[str, str]:
        return get_cors_headers(
            self.app_config.cors_origin, additional_headers=['x-hub-signature-256']
        )

    @override
    async def handle(self, request: Request) -> JSONResponse:
        body = await request.body()
        verify_resp = self.verify_signature(request, body)
        if verify_resp:
            return verify_resp

        headers = self.get_cors_headers()

        try:
            payload = await self.verify_json_payload(request)
        except Exception as e:
            msg = f'could not parse JSON body: {e}'
            logger.info(msg)
            return JSONResponse(status_code=400, content=dict(error=msg), headers=headers)

        logger.debug(f'github webhook payload: {payload}')
        self.process_payload(payload)
        return JSONResponse(status_code=200, content='OK', headers=headers)

    def process_payload(self, payload: dict[str, Any]) -> None:
        pass

    def verify_signature(self, request: Request, body: bytes) -> JSONResponse | None:
        """Verify the GitHub X-Hub-Signature-256 header.

        Returns a JSONResponse on failure, or None on success.
        """
        assert self.app_config.github

        signature = request.headers.get('x-hub-signature-256')

        if not signature:
            msg = 'request denied; missing X-Hub-Signature-256 header'
            logger.info(msg)
            return self.deny_request(msg)

        try:
            sig_prefix, sig_hex = signature.split('=', 1)
        except Exception:
            msg = f'request denied; malformed X-Hub-Signature-256 header: {signature}'
            logger.info(msg)
            return self.deny_request(msg)

        if sig_prefix.lower() != 'sha256':
            msg = f'request denied; unsupported X-Hub-Signature-256 prefix: {sig_prefix}'
            logger.info(msg)
            return self.deny_request(msg)

        mac = hmac.new(
            self.app_config.github.hmac.encode('utf-8'), msg=body, digestmod=hashlib.sha256
        )
        expected = mac.hexdigest()
        if not hmac.compare_digest(expected, sig_hex):
            msg = 'request denied; content does not match X-Hub-Signature-256'
            logger.info(msg)
            return self.deny_request(msg)

        return None

    async def verify_json_payload(self, request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception as e:
            msg = f'failed to parse JSON payload: {e}'
            raise InvalidPayloadError(msg) from e
        if not payload:
            msg = 'empty payload'
            raise InvalidPayloadError(msg)
        if not isinstance(payload, dict):
            msg = 'payload is not a dict'
            raise InvalidPayloadError(msg)
        # keep pyright happy with the cast while ignoring mypy's perfectly sensible warning
        p = cast(dict[Any, Any], payload)  # type: ignore[redundant-cast]
        if not all(isinstance(key, str) for key in p):
            msg = 'payload keys are not all strings'
            raise InvalidPayloadError(msg)
        return p

    def deny_request(self, msg: str) -> JSONResponse:
        return JSONResponse(
            status_code=401, content=dict(error=msg), headers=self.get_cors_headers()
        )
