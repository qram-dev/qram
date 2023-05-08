import time
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any, Callable, cast

import jwt
from requests import Response, request

from qram.config import Config
from qram.web.provider import Pr, ProviderApi, ProviderRepoApi


logger = getLogger()

# Github API requires you to provide ID and private key in exchange for an
# access token that can also expire in an hour. Wrap all that into self-repairing
# object and hope it does not break.


def github_api(cfg: Config) -> 'Github':
    '''Factory function providing a working and self-repairing instance of Github API
    '''
    assert cfg.app.github, 'config have to be setup for github'
    jwt_payload = {
        # issued at ...
        'iat': int(time.time()),
        # JWT expiration time (10 minutes maximum)
        'exp': int(time.time()) + 600,
        # github app identifier
        'iss': cfg.app.github.app_id
    }
    encoded_jwt = jwt.encode(jwt_payload, cfg.app.github.pem, algorithm="RS256")
    url = f'https://api.github.com/app/installations/{cfg.app.github.installation_id}/access_tokens'

    def get_token() -> tuple[str, datetime]:
        logger.debug('requesting new access token from github')
        r = request('POST', url, headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {encoded_jwt}',
            'X-GitHub-Api-Version': '2022-11-28',
        })

        if not r.ok:
            msg = f'github JWT authorization failed with {r.status_code}:\n{r.content.decode()}'
            logger.error(msg)
            raise RuntimeError(msg)
        j = r.json()
        expires = datetime.fromisoformat(j['expires_at'].rstrip('Z')) - timedelta(minutes=5)
        token = j['token']
        logger.debug(f'token acquired, expires at {expires}')
        return (token, expires)
    return Github(*get_token(), get_token)


class Github(ProviderApi):
    def __init__(
            self, token: str, expires_at: datetime,
            reinitialize: Callable[[], tuple[str, datetime]]
        ) -> None:
        self.token = token
        self.expires_at = expires_at
        self.reinitialize = reinitialize

    def _request(self, method: str, destination: str, **kwargs: Any) -> Response:
        now = datetime.now()
        if now > self.expires_at:
            self.token, self.expires_at = self.reinitialize()
        headers = dict(Authorization=f'Bearer {self.token}')
        h = cast(dict[str, Any], kwargs.get('headers', dict()))
        if h:
            headers.update(h)

        destination = destination.lstrip('/')
        r = request(
            method=method,
            url=f'https://api.github.com/{destination}',
            headers=headers,
            **kwargs,
        )
        logger.debug(f'{method} -> {r.status_code}')
        return r

    def get(self, destination: str, **kwargs: Any) -> Response:
        return self._request('GET', destination, **kwargs)

    def post(self, destination: str, **kwargs: Any) -> Response:
        return self._request('POST', destination, **kwargs)

    def put(self, destination: str, **kwargs: Any) -> Response:
        return self._request('PUT', destination, **kwargs)

    def repo(self, owner: str, repo: str) -> 'GithubRepo':
        return GithubRepo(self, owner, repo)


class GithubRepo(ProviderRepoApi):
    def __init__(self, gh: Github, owner: str, repo: str) -> None:
        self.api = gh
        self.owner = owner
        self.repo = repo


    def create_pr(self, branch: str, title: str) -> Response:
        r = self.api.post(f'repos/{self.owner}/{self.repo}/pulls', json=dict(
            title=title,
            head=branch,
            base='main',
        ))
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
            author=dict(
                username=j['user']['login'],
                id=j['user']['id']
            )
        )
