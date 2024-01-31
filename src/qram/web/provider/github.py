import time
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any, Callable, cast

import jwt
from requests import Response, request

from qram.config import AppConfig
from qram.web.provider import Pr, ProviderApi, ProviderRepoApi

logger = getLogger(__name__)

# Github API is weird.
# Some endpoints require you to generate JWT from private PEM and App id.
# For others you need to first acquire separate access token from API using said JWT.
# JWT expire in 10 minutes, access tokens expire in 1 hour.
# Wrap everything into self-repairing objects and hope for the best.


def github_api(cfg: AppConfig) -> 'Github':
    """Factory function providing a working and self-repairing instance of Github API"""
    github = cfg.github
    assert github is not None, 'config have to be setup for github'

    def rejwt() -> str:
        jwt_payload = {
            # issued at ...
            'iat': int(time.time()),
            # JWT expiration time (10 minutes maximum)
            'exp': int(time.time()) + 600,
            # github app identifier
            'iss': github.app_id,
        }
        return jwt.encode(jwt_payload, github.pem, algorithm='RS256')

    url = f'https://api.github.com/app/installations/{github.installation_id}/access_tokens'

    def get_token() -> tuple[str, datetime]:
        encoded_jwt = rejwt()
        logger.debug('requesting new access token from github')
        r = request(
            'POST',
            url,
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {encoded_jwt}',
                'X-GitHub-Api-Version': '2022-11-28',
            },
        )

        if not r.ok:
            msg = f'github JWT authorization failed with {r.status_code}:\n{r.content.decode()}'
            logger.error(msg)
            raise RuntimeError(msg)
        j = r.json()
        expires = datetime.fromisoformat(j['expires_at'].rstrip('Z')) - timedelta(minutes=5)
        token = j['token']
        logger.debug(f'token acquired, expires at {expires}')
        return (token, expires)

    return Github(*get_token(), get_token, rejwt)


class Github(ProviderApi):
    def __init__(
        self,
        token: str,
        expires_at: datetime,
        reinitialize: Callable[[], tuple[str, datetime]],
        rejwt: Callable[[], str],
    ) -> None:
        self.token = token
        self.expires_at = expires_at
        self.reinitialize = reinitialize
        self.rejwt = rejwt

    def _request(
        self, method: str, destination: str, use_jwt: bool = False, **kwargs: Any
    ) -> Response:
        now = datetime.now()
        if use_jwt:
            token = self.rejwt()
        else:
            if now > self.expires_at:
                self.token, self.expires_at = self.reinitialize()
            token = self.token
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

        destination = destination.lstrip('/')
        url = f'https://api.github.com/{destination}'
        logger.debug(f'{method} -> {url}')
        h = cast(dict[str, Any], kwargs.get('headers', dict()))
        if h:
            logger.debug(f'HEADERS : {h}')
            headers.update(h)

        r = request(
            method=method,
            url=url,
            headers=headers,
            **kwargs,
        )
        logger.debug(f'{method} => {r.status_code}')
        return r

    def get(self, destination: str, **kwargs: Any) -> Response:
        return self._request('GET', destination, **kwargs)

    def post(self, destination: str, **kwargs: Any) -> Response:
        return self._request('POST', destination, **kwargs)

    def put(self, destination: str, **kwargs: Any) -> Response:
        return self._request('PUT', destination, **kwargs)

    def repo(self, owner: str, repo: str) -> 'GithubRepo':
        return GithubRepo(self, owner, repo)

    def configure_webhook(self, config: AppConfig) -> None:
        gh = config.github
        assert gh
        assert gh.webhook_url
        msg = f'github: app={gh.app_id} installation={gh.installation_id}: reconfigure webhook to '
        msg += gh.webhook_url
        if config.hmac:
            msg += ' (with HMAC secret)'
        logger.info(msg)
        payload = dict(
            url=gh.webhook_url,
            content_type='json',
            secret=config.hmac,
        )
        r = self._request('PATCH', 'app/hook/config', json=payload, use_jwt=True)
        if not r.ok:
            raise RuntimeError(r.content.decode())

    def repo_clone_url(self, repo: str) -> str:
        now = datetime.now()
        if now > self.expires_at:
            self.token, self.expires_at = self.reinitialize()
        return f'https://x-access-token:{self.token}@github.com/{repo}.git'


class GithubRepo(ProviderRepoApi):
    def __init__(self, gh: Github, owner: str, repo: str) -> None:
        self.api = gh
        self.owner = owner
        self.repo = repo

    def create_pr(self, branch: str, title: str) -> Response:
        r = self.api.post(
            f'repos/{self.owner}/{self.repo}/pulls',
            json=dict(
                title=title,
                head=branch,
                base='main',
            ),
        )
        logger.info(f'created PR: {r.json().get("html_url")}')
        return r

    def get_pr(self, pr: int) -> 'Pr':
        r = self.api.get(f'repos/{self.owner}/{self.repo}/pulls/{pr}')
        j = r.json()
        head = j.get('head', dict()).get('ref')
        if not head:
            raise RuntimeError('no head')
        return Pr(
            number=pr,
            title=j['title'],
            body=j.get('body') or '',
            branch_head=head,
            author=dict(username=j['user']['login'], id=j['user']['id']),
        )
