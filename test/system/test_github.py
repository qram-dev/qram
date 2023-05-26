import logging
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest

from qram.config import Config
from qram.globals import WORKDIR
from qram.web.provider.github import Github, github_api

from test import chdir
from test.system import BetterCaplog, ServerThread, wait_for


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
    return Config.github_config_from_env()


@pytest.fixture(scope='module')
def api(config: Config) -> Github:
    return github_api(config)


@pytest.fixture(scope='module')
def webhook_reconfigured(api: Github, config: Config) -> None:
    assert config.app.github
    logger.info('⬜  reconfiguring Github App webhook url ...')
    api.configure_webhook(config)
    logger.info('🟩  webhook reconfigured')


@pytest.mark.sysA
def test_whoami(api: Github) -> None:
    r = api.get('/installation/repositories')
    assert r.ok
    j = r.json()
    assert j['total_count'] > 0
    assert f'{ORG}/{REPO}' in (x['full_name'] for x in j['repositories'])


@pytest.mark.sysA
def test_token_reinitialization(api: Github) -> None:
    old_expires = api.expires_at
    old_token = api.token

    r = api.get('/installation/repositories')
    assert r.ok

    middle_expires = api.expires_at
    middle_token = api.token
    assert middle_expires == old_expires
    assert middle_token == old_token

    api.expires_at = datetime.utcnow()
    r = api.get('/installation/repositories')
    assert r.ok

    assert api.token != old_token
    assert api.expires_at > datetime.utcnow()


@pytest.mark.sysA
def test_get_pr(api: Github) -> None:
    pr = api.repo(ORG, REPO).get_pr(1)
    assert pr.number == 1
    assert pr.author['username'] == 'Artalus'
    assert pr.title == 'Neverclosing PR for system tests'


@pytest.mark.sysA
def test_app_start_stop(config: Config, better_caplog: BetterCaplog) -> None:
    server_thread = ServerThread(config, debug=False)
    with server_thread:
        wait_for(
            better_caplog.log_contains('Pong!'),
            'PingEvent never got processed',
        )


@pytest.mark.sysA
def test_app_initialize_repos(config: Config, better_caplog: BetterCaplog) -> None:
    better_caplog.set_level(logging.INFO, logger='qram.web.server')
    server_thread = ServerThread(config, debug=False, initialize_repos=True)
    with server_thread:
        wait_for(
            better_caplog.log_contains('Initialization done'),
            'repos never got initialized',
            attempts=10,
            sleep_mult=2
        )
        assert (WORKDIR / ORG / REPO / 'README.md').is_file(), 'repo was not checked out'


@pytest.mark.sysB
def test_comment_reaction(config: Config, api: Github, better_caplog: BetterCaplog,
                          webhook_reconfigured: None) -> None:
    better_caplog.set_level(logging.INFO, logger='qram.web')
    better_caplog.set_level(logging.INFO, logger='qram.web.server')
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
                better_caplog.log_contains('this is PR comment'),
                'webhook never got "comment" event',
            )
            logger.info('🟩  got it')

            logger.info('⬜  check if worker processed it...')
            wait_for(
                better_caplog.log_contains('It is meant for us'),
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
