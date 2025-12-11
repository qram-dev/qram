import time
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any

import httpx
import jwt
from httpx import Response

from qram.config import AppConfig

logger = getLogger(__name__)

# TODO: make it configurable?
REQUESTS_TIMEOUT = 30

# Github API is weird.
# Some endpoints require you to generate JWT from private PEM and App id.
# For others you need to first acquire separate access token from API using said JWT.
# JWT expires in 10 minutes, access tokens expire in 1 hour.
# Wrap everything into self-repairing objects and hope for the best.
# https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app


class GithubApi:
    app_id: str
    pem: str
    installation_tokens_url: str
    token: str
    expires_at: datetime

    def __init__(self, cfg: AppConfig) -> None:
        github = cfg.github
        assert github is not None, 'config have to be setup for github'

        self.app_id = github.app_id
        self.pem = github.pem
        self.installation_tokens_url = (
            f'https://api.github.com/app/installations/{github.installation_id}/access_tokens'
        )
        self.token, self.expires_at = self.get_token()

    def rejwt(self) -> str:
        # ""we recommend that you set this 60 seconds in the past""
        t = int(time.time()) - 60
        jwt_payload: dict[str, Any] = {
            # issued at ...
            'iat': t,
            # JWT expiration time (10 minutes maximum)
            'exp': t + 600,
            # github app identifier
            'iss': self.app_id,
        }
        return jwt.encode(jwt_payload, self.pem, algorithm='RS256')

    def get_token(self) -> tuple[str, datetime]:
        encoded_jwt = self.rejwt()
        logger.debug('requesting new access token from github')
        r = httpx.request(
            'POST',
            self.installation_tokens_url,
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {encoded_jwt}',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            timeout=REQUESTS_TIMEOUT,
        )

        # TODO: assuming this is a network hiccup: should pause and reattempt in a bit
        if not r.is_success:
            msg = f'github JWT authorization failed with {r.status_code}:\n{r.content.decode()}'
            logger.error(msg)
            raise RuntimeError(msg)
        j = r.json()
        expires = datetime.fromisoformat(j['expires_at'].rstrip('Z')).replace(
            tzinfo=UTC
        ) - timedelta(minutes=5)
        token = j['token']
        logger.debug(f'token acquired, expires at {expires}')
        return (token, expires)

    def _request(
        self,
        method: str,
        destination: str,
        *,
        use_jwt: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> Response:
        now = datetime.now(tz=UTC)
        if use_jwt:
            auth = self.rejwt()
        else:
            if now > self.expires_at:
                self.token, self.expires_at = self.get_token()
            auth = self.token
        headers = {
            'Authorization': f'Bearer {auth}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

        destination = destination.lstrip('/')
        url = f'https://api.github.com/{destination}'
        logger.debug(f'{method} -> {url}')
        # TODO: is it needed at all?..
        h = kwargs.get('headers', dict())
        if h:
            logger.debug(f'  HEADERS : {h}')
            headers.update(h)

        r = httpx.request(
            method=method,
            url=url,
            headers=headers,
            timeout=REQUESTS_TIMEOUT,
            **kwargs,
        )
        logger.debug(f'{method} => {r.status_code}')
        return r

    def http_get(self, destination: str, *, use_jwt: bool = False, **kwargs: object) -> Response:
        return self._request('GET', destination, use_jwt=use_jwt, **kwargs)

    def http_post(self, destination: str, *, use_jwt: bool = False, **kwargs: object) -> Response:
        return self._request('POST', destination, use_jwt=use_jwt, **kwargs)

    def http_delete(self, destination: str, *, use_jwt: bool = False, **kwargs: object) -> Response:
        return self._request('DELETE', destination, use_jwt=use_jwt, **kwargs)

    def http_put(self, destination: str, *, use_jwt: bool = False, **kwargs: object) -> Response:
        return self._request('PUT', destination, use_jwt=use_jwt, **kwargs)

    def http_patch(self, destination: str, *, use_jwt: bool = False, **kwargs: object) -> Response:
        return self._request('PATCH', destination, use_jwt=use_jwt, **kwargs)
