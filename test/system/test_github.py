import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Generator

import pytest

import qram.config
from qram.config import Config
from qram.web.provider.github import Github, github_api
from test.system import ServerThread
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
    c.app.github = qram.config._CfgGithub(
        app_id = os.environ['QRAM_APP_GITHUB_APP_ID'],
        installation_id = os.environ['QRAM_APP_GITHUB_INSTALLATION_ID'],
        pem = Path(os.environ['QRAM_APP_GITHUB_PEM_FILE']).read_text().strip(),
    )
    return c

@pytest.fixture(scope='module')
def api(config: Config) -> Github:
    api = github_api(config)

    return api


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
