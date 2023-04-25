import logging

from pprint import pformat
from typing import NamedTuple

from requests import get, post, put, Response

class Github:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo

    def get(self, destination: str, **kwargs) -> Response:
        headers = dict(Authorization=f'Bearer {self.token}')
        h = kwargs.get('headers', dict())
        if h:
            headers.update(h)
        r = get(
            f'https://api.github.com/repos/{self.owner}/{self.repo}/{destination}',
            headers=headers,
            **kwargs,
        )
        logging.info(f'GET -> {r.status_code}')
        return r

    def post(self, destination: str, **kwargs) -> Response:
        headers = dict(Authorization=f'Bearer {self.token}')
        h = kwargs.get('headers', dict())
        if h:
            headers.update(h)
        return post(
            f'https://api.github.com/repos/{self.owner}/{self.repo}/{destination}',
            headers=headers,
            **kwargs,
        )

    def put(self, destination: str, **kwargs) -> Response:
        headers = dict(Authorization=f'Bearer {self.token}')
        h = kwargs.get('headers', dict())
        if h:
            headers.update(h)
        return put(
            f'https://api.github.com/repos/{self.owner}/{self.repo}/{destination}',
            headers=headers,
            **kwargs,
        )

    def create_pr(self, branch: str, title: str) -> Response:
        r = self.post('pulls', json=dict(
            title=title,
            head=branch,
            base='main',
        ))
        logging.info(f'created PR: {r.json().get("html_url")}')
        return r

    def get_pr(self, pr: int) -> 'Pr':
        r = self.get(f'pulls/{pr}')
        j = r.json()
        head = j.get('head', dict()).get('ref')
        if not head:
            raise RuntimeError('no head')
        logging.debug(f'pr:\n'+pformat(j))
        return Pr(
            number=pr,
            title=j['title'],
            body=j.get('body') or '',
            branch_head=head,
        )

class Pr(NamedTuple):
    number: int
    title: str
    body: str
    branch_head: str
