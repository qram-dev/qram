import asyncio
import logging
import time
from threading import Thread
from typing import Any, Callable

from requests import get, post

from qram.config import Config
from qram.web.server import make_server


logger = logging.getLogger(__name__)


class ServerThread(Thread):
    exception: Exception | None
    timeout: float | None

    def __init__(self, debug: bool, config: Config, timeout: float=10):
        super().__init__(name=f'Qram-{config.app.provider}:{config.app.port}')
        self.debug = debug
        self.config = config
        self.timeout = timeout
        self.exception = None

    def run(self) -> None:
        try:
            asyncio.run(make_server(self.debug, self.config, True))
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

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        logger.info('◀◀◀ stopping webhook server ...')
        r = post(f'http://localhost:{self.config.app.port}/stop')
        assert r.ok
        assert r.content == b'Goodbye.'
        self.join(self.timeout)
        logger.info('◀◀◀ stopped')
        if self.exception:
            raise self.exception


def wait_for(check: Callable[[], bool], errmsg: str, attempts: int=5) -> None:
    exception = None
    for i in range(attempts + 1):
        try:
            if check():
                return
        except Exception as e:
            exception = e
        time.sleep(i)
    if exception:
        raise TimeoutError(f'{errmsg} after {attempts} checks') from exception
    else:
        raise TimeoutError(f'{errmsg} after {attempts} checks')
