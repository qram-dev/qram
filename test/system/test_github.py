from datetime import datetime
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Callable, Generator

import pytest

import qram.config
from qram.config import Config
from qram.web.provider.github import Github, github_api
from test.system import ServerThread, wait_for
from .. import chdir


# these are under our protection
# pyright: reportPrivateUsage=false

ORG = 'qram-dev'
REPO = 'test-system-deadbeef'
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def chtmp(tmp_path: Path) -> Generator[None, None, None]:
    with chdir(tmp_path):
        yield

@pytest.fixture(scope='module')
def config() -> Config:
    c = deepcopy(qram.config._defaults)
    c.app.hmac = os.environ['QRAM_APP_HMAC']
    c.app.provider = 'github'
    pem = os.environ.get('QRAM_APP_GITHUB_PEM')
    if pem is None:
        pem = Path(os.environ['QRAM_APP_GITHUB_PEM_FILE']).read_text()
    c.app.github = qram.config._CfgGithub(
        app_id = os.environ['QRAM_APP_GITHUB_APP_ID'],
        installation_id = os.environ['QRAM_APP_GITHUB_INSTALLATION_ID'],
        pem = pem.strip(),
    )
    return c

@pytest.fixture(scope='module')
def api(config: Config) -> Github:
    api = github_api(config)

    return api

@pytest.fixture(scope='module')
def webhook_reconfigured(api: Github, config: Config) -> None:
    url = os.environ['QRAM_WEBHOOK_URL']
    logger.info(f'⬜  reconfiguring Github App webhook url to -> {url} ...')
    payload = dict(
        url=url,
        content_type='json',
        secret=config.app.hmac,
    )
    r = api._request('PATCH', 'app/hook/config', json=payload, use_jwt=True)
    if not r.ok:
        raise RuntimeError(r.content.decode())
    logger.info('🟩  webhook reconfigured')


@pytest.mark.sysA
def test_whoami(api: Github) -> None:
    r = api.get('/installation/repositories')
    assert r.ok
    j = r.json()
    assert j['total_count'] > 0
    assert f'{ORG}/{REPO}' in (x['full_name'] for x in j['repositories'])


@pytest.mark.sysA
def test_get_pr(api: Github) -> None:
    pr = api.repo(ORG, REPO).get_pr(1)
    assert pr.number == 1
    assert pr.author['username'] == 'Artalus'
    assert pr.title == 'Neverclosing PR for system tests'


@pytest.mark.sysA
def test_app_start_stop(config: Config) -> None:
    server_thread = ServerThread(False, config)
    with server_thread:
        pass
        # wait_for((Path(ORG) / REPO / 'README.md').is_file, 'repo was not checked out')


@pytest.mark.sysB
def test_comment_reaction(config: Config, api: Github, caplog: pytest.LogCaptureFixture,
                          webhook_reconfigured: None) -> None:
    caplog.set_level(logging.INFO, logger='qram.web')
    caplog.set_level(logging.INFO, logger='qram.web.server')
    server_thread = ServerThread(True, config)
    with server_thread:
        message = f'beep-boop, i\'m a bot, time is {datetime.now()}'
        logger.info(f'⬜  posting a new comment to PR #1 in {ORG}/{REPO}...')
        payload = dict(
            body=message
        )
        r = api.post(f'/repos/{ORG}/{REPO}/issues/1/comments', json=payload)
        if not r.ok:
            raise RuntimeError(r.content.decode())
        new_comment_id = r.json()['id']

        logger.info('🟩  comment posted')
        logger.info('⬜  check if webhook got it...')
        try:
            wait_for(
                log_contains(caplog, 'this is PR comment'),
                'webhook never got "comment" event'
            )
            logger.info('🟩  got it')
            logger.info('⬜  check if worker processed it...')
            wait_for(
                log_contains(caplog,
                    'ma, look, event! PrCommentEvent'),
                'PrCommentEvent never got processed'
            )
            logger.info('🟩  processed')
        finally:
            logger.info(f'⬜  deleting freshly posted comment {new_comment_id}...')
            payload = dict(
                body=message
            )
            r = api._request('DELETE', f'/repos/{ORG}/{REPO}/issues/comments/{new_comment_id}')
            if not r.ok:
                raise RuntimeError(r.content.decode())
            logger.info('🟩  comment deleted')


def log_contains(capture: pytest.LogCaptureFixture, msg: str) -> Callable[[], bool]:
    def contains() -> bool:
        for record in capture.records:
            if msg in record.message:
                return True
        return False
    return contains

logging.basicConfig(level=logging.INFO)
