import logging
import os
from collections.abc import Callable, Generator
from datetime import datetime
from pathlib import Path

import pytest

import qram.config
from qram.config import Config
from qram.web.provider.github import Github, github_api

from test import chdir
from test.system import ServerThread, wait_for


# these are under our protection
# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001, ARG001

ORG = 'qram-dev'
REPO = 'test-system-deadbeef'
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def chtmp(tmp_path: Path) -> Generator[None, None, None]:
    with chdir(tmp_path):
        yield


@pytest.fixture(scope='module')
def config() -> Config:
    c = Config.construct()
    c.app.hmac = os.environ['QRAM_APP_HMAC']
    pem = os.environ.get('QRAM_APP_GITHUB_PEM')
    if pem is None:
        pem = Path(os.environ['QRAM_APP_GITHUB_PEM_FILE']).read_text()
    c.app.github = qram.config._CfgGithub.construct(
        app_id = os.environ['QRAM_APP_GITHUB_APP_ID'],
        installation_id = os.environ['QRAM_APP_GITHUB_INSTALLATION_ID'],
        pem = pem.strip(),
    )
    return c


@pytest.fixture(scope='module')
def api(config: Config) -> Github:
    return github_api(config)


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
def test_app_start_stop(config: Config, caplog: pytest.LogCaptureFixture) -> None:
    server_thread = ServerThread(config, debug=False)
    with server_thread:
        wait_for(
            log_contains(caplog, 'Pong!'),
            'PingEvent never got processed',
        )


@pytest.mark.skip
@pytest.mark.sysA
def test_app_initialize_repos(config: Config, caplog: pytest.LogCaptureFixture) -> None:
    # FIXME: no checkouts done during initialization yet. This test here is just so I won't forget
    # to actually test it
    server_thread = ServerThread(config, debug=False, initialize_repos=True)
    with server_thread:
        wait_for(
            log_contains(caplog, 'Initialization done'),
            'repos never got initialized',
        )
        assert (Path(ORG) / REPO / 'README.md').is_file(), 'repo was not checked out'


@pytest.mark.sysB
def test_comment_reaction(config: Config, api: Github, caplog: pytest.LogCaptureFixture,
                          webhook_reconfigured: None) -> None:
    caplog.set_level(logging.INFO, logger='qram.web')
    caplog.set_level(logging.INFO, logger='qram.web.server')
    server_thread = ServerThread(config, debug=True)
    with server_thread:
        message = f"!qram\nbeep-boop, i'm a bot, time is {datetime.now()}"  # noqa: DTZ005
        logger.info(f'⬜  posting a new comment to PR #1 in {ORG}/{REPO}...')
        payload = dict(body=message)
        r = api.post(f'/repos/{ORG}/{REPO}/issues/1/comments', json=payload)
        if not r.ok:
            logger.error(f'🟥  post failed: {r.content.decode()}')
            raise RuntimeError(r.content.decode())
        new_comment_id = r.json()['id']
        logger.info('🟩  comment posted')

        logger.info('⬜  check if webhook got it...')
        try:
            wait_for(
                log_contains(caplog, 'this is PR comment'),
                'webhook never got "comment" event',
            )
            logger.info('🟩  got it')

            logger.info('⬜  check if worker processed it...')
            wait_for(
                log_contains(caplog,
                    'It is meant for us'),
                'PrCommentEvent never got processed',
            )
            logger.info('🟩  processed')
        except Exception as e:
            logger.error(f'🟥  exception: {e}')  # noqa: TRY400
            raise
        finally:
            logger.info(f'⬜  deleting freshly posted comment {new_comment_id}...')
            payload = dict(
                body=message,
            )
            r = api._request('DELETE', f'/repos/{ORG}/{REPO}/issues/comments/{new_comment_id}')
            if not r.ok:
                logger.error(f'🟥  delete failed: {r.content.decode()}')
                raise RuntimeError(r.content.decode())
            logger.info('🟩  comment deleted')


def log_contains(capture: pytest.LogCaptureFixture, msg: str) -> Callable[[], bool]:
    def contains() -> bool:
        return any(msg in record.message for record in capture.records)
    return contains

logging.basicConfig(level=logging.INFO)
