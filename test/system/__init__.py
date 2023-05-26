import asyncio
import logging
import time
from collections.abc import Callable
from threading import Thread
from typing import Any

import pytest
from requests import get, post

from qram.config import Config
from qram.web.server import make_server


logger = logging.getLogger(__name__)


class ServerThread(Thread):
    exception: Exception | None
    timeout: float | None

    def __init__(self, config: Config, *, debug: bool, initialize_repos: bool=False,
                 timeout: float=10):
        super().__init__(name=f'Qram-{config.app.provider}:{config.app.port}')
        self.debug = debug
        self.config = config
        self.timeout = timeout
        self.initialize_repos = initialize_repos
        self.exception = None

    def run(self) -> None:
        try:
            asyncio.run(make_server(self.config, debug=self.debug, provide_stop=True,
                                    initialize_repos=self.initialize_repos))
        except Exception as e:
            self.exception = e

    def __enter__(self) -> None:
        logger.info('▶▶▶ starting webhook server ...')
        self.start()

        def server_started() -> bool:
            r = get(f'http://localhost:{self.config.app.port}', timeout=1)
            return r.ok and r.content == b'qram'
        wait_for(server_started, f'qram did not start on port {self.config.app.port}')
        logger.info('▶▶▶ started')

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:  # noqa: ANN401
        # TODO: handle exceptions somehow?
        logger.info('◀◀◀ stopping webhook server ...')
        r = post(f'http://localhost:{self.config.app.port}/stop')
        assert r.ok
        assert r.content == b'Goodbye.'
        self.join(self.timeout)
        logger.info('◀◀◀ stopped')
        if self.exception:
            raise self.exception


def wait_for(check: Callable[[], bool], errmsg: str, *, attempts: int=5, sleep_mult: float=1) \
    -> None:
    exception = None
    for att in range(1, attempts + 2):
        logger.debug(f'waiting for {check}, attempt #{att}')
        try:
            if check():
                return
        except Exception as e:
            exception = e
        time.sleep(att*sleep_mult)
    errmsg = f'{errmsg} after {attempts} checks'
    logger.error(f'🟥  {errmsg}')
    if exception:
        raise TimeoutError(errmsg) from exception
    raise TimeoutError(errmsg)


class BetterCaplog:
    def __init__(self, caplog: pytest.LogCaptureFixture) -> None:
        self.caplog = caplog

    def set_level(self, level: int, logger: str) -> None:
        current_log_level = logging.getLogger(logger).getEffectiveLevel()
        assert current_log_level > logging.NOTSET, 'effective logging should be at least WARNING?!'
        if current_log_level > level:
            self.caplog.set_level(level, logger)

    def log_contains(self, msg: str) -> Callable[[], bool]:
        def contains() -> bool:
            return any(msg in record.message for record in self.caplog.records)
        return contains
