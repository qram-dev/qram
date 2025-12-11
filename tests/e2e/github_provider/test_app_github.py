import logging
import os
import threading
import time

import httpx
import pytest
from dotenv import load_dotenv

from qram.config import AppConfig
from qram.web.app import create_app, run_app
from qram.web.github import GithubApi

logger = logging.getLogger(__name__)

# TODO: make configurable?
OWNER = 'qram-dev'
REPO = 'test-system-deadbeef'


@pytest.fixture(scope='module')
def config() -> AppConfig:
    _ = load_dotenv()
    return AppConfig.config_from_env()


@pytest.fixture(scope='module')
def server_thread(config: AppConfig) -> None:
    # Run server in a thread
    thread = threading.Thread(
        target=run_app,
        args=(create_app(config), config),
        kwargs=dict(debug=True),
        daemon=True,
    )
    thread.start()
    # Wait for server to be ready by polling /ping endpoint
    start = time.time()
    timeout = 10  # seconds
    url = f'http://{config.bind_to}:{config.port}/ping'
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=1)
            if r.is_success:
                logger.info(f'Server is ready at {url}')
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.1)
    else:
        msg = f'Server failed to start within {timeout} seconds'
        raise RuntimeError(msg)

    # thread dies when main process exits due to daemon=True


# some pytest fixtures are doomed to be unused
# ruff: noqa: ARG001


def test_webhook_reception(
    config: AppConfig, server_thread: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Trigger a GitHub event and verify the webhook receives it."""
    assert config.github

    gh = GithubApi(config)

    logger.info(f'Triggering event on {OWNER}/{REPO}')
    with caplog.at_level(logging.DEBUG, logger='qram.web'):
        r = gh.http_post(
            # github uses /issues/ both for actual issues and PRs
            f'repos/{OWNER}/{REPO}/issues/1/comments',
            json=dict(body=os.environ['PYTEST_CURRENT_TEST']),
        )
        assert r.is_success, f'Failed to post comment: {r.content.decode()}'

        start = time.time()
        received = False
        while time.time() - start < 60:
            for record in caplog.records:
                if 'github webhook payload' in record.message:
                    received = True
                    break
            if received:
                break
            time.sleep(1)
        else:
            assert received, 'Webhook event was not received within 60 seconds'

        # remove the comment we just posted
        comment_id = r.json().get('id')

        r_del = gh.http_delete(f'repos/{OWNER}/{REPO}/issues/comments/{comment_id}')
        if not r_del.is_success:
            logger.warning(f'Failed to delete comment: {r_del.content.decode()}')
