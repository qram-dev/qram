import logging
import sys
import threading
import time
from argparse import ArgumentParser
from dataclasses import dataclass

import httpx
import uvicorn
from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


@dataclass
class Args:
    token: str
    port: int
    timeout: int


def parse_args() -> Args:
    p = ArgumentParser()
    _ = p.add_argument('--token', required=True)
    _ = p.add_argument('--port', type=int, required=True)
    _ = p.add_argument('--timeout', type=int, default=60)
    return Args(**p.parse_args().__dict__)


def send_request(token: str, attempt: int) -> None:
    url = f'https://webhook.site/{token}/waitforwhcli'
    logger.info(f'Sending request #{attempt} to {url}')
    try:
        _ = httpx.get(url, params={'attempt': attempt}, timeout=5)
    except Exception:
        logger.exception('failed to send request')


def main(args: Args) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    logger.info(f'Starting server on localhost:{args.port}')

    app = FastAPI()
    request_received = threading.Event()
    # silly "closure" to access server object from handler
    server_holder: dict[str, uvicorn.Server] = dict()

    @app.get('/waitforwhcli')
    async def wait_endpoint(request: Request) -> str:
        logger.info(f'Request received: {request.method} {request.url}')
        request_received.set()
        # try to request uvicorn shutdown as soon as we receive the webhook
        try:
            server_holder['server'].should_exit = True
        except Exception:
            logger.exception('failed to request server shutdown from handler')
        return 'OK'

    server_cfg = uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='warning')
    server = uvicorn.Server(server_cfg)
    server_holder['server'] = server
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1)

    logger.info(f'Sending GET requests until received (timeout: {args.timeout}s)...')
    start_time = time.time()
    attempt = 0

    while time.time() - start_time < args.timeout:
        # can't cleanly shutdown uvicorn.run from another thread easily without complex logic
        # exit() should kill the daemon thread
        if not server_thread.is_alive() and not server.should_exit:
            logger.error('server thread exited unexpectedly; failing immediately')
            sys.exit(2)
        if request_received.is_set():
            elapsed = time.time() - start_time
            logger.info(f'Success! Request received after {elapsed:.1f}s - whcli is operational!')
            # ensure server shuts down and thread is joined
            try:
                server_holder['server'].should_exit = True
            except Exception:
                logger.exception('failed to request server shutdown from main')
            server_thread.join(2)
            sys.exit(0)
        attempt += 1
        send_request(args.token, attempt)
        time.sleep(1)

    logger.error(f'Timeout after {args.timeout}s - no requests received. whcli may not be ready.')
    sys.exit(1)


if __name__ == '__main__':
    main(parse_args())
