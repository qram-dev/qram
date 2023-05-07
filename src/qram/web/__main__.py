#!/usr/bin/env python3
import asyncio
import logging
from argparse import ArgumentParser
from dataclasses import dataclass

from meiga import Failure, Success
from tornado.queues import Queue
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop

from . import ExpectedError, GithubWebhook, ProviderEvent, StopEvent, Webhook
from qram.config import Config


logger = logging.getLogger(__name__)


# pylance has issues understanding inheritance in tornado
#   pyright: reportIncompatibleMethodOverride=false


@dataclass
class Args:
    debug: bool


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('--debug', action='store_true')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    asyncio.run(amain(args.debug))


class MainHandler(RequestHandler):
    def get(self) -> None:
        self.write('qram')

class WebhookHandler(RequestHandler):
    webhook: Webhook
    debug: bool

    def initialize(self, token: str|None, webhook: Webhook, debug: bool) -> None:
        self.token = token.encode('utf-8') if token else None
        self.webhook = webhook
        self.debug = debug

    def options(self) -> None:
        if self.debug:
            self.add_header('Access-Control-Allow-Headers', 'x-hub-signature-256')
            self.add_header('Access-Control-Allow-Origin', 'https://webhook.site')

    def post(self) -> None:
        logger.info('-'*80)
        if self.debug:
            self.add_header('Access-Control-Allow-Headers', 'x-hub-signature-256')
            self.add_header('Access-Control-Allow-Origin', 'https://webhook.site')

        match self.webhook.verify_request(self.token, self.request):
            case Success(True):
                logger.info('request verified')
            case Failure(ExpectedError()) as e:
                logger.info('request unverified')
                self.set_status(403, e.get_value().message)
                return
            case _ as e:
                raise RuntimeError(f'unexpected verification result: {e}')

        match self.webhook.store_request(self.request):
            case Success(True):
                logger.info('request processed and event stored')
            case Success(False):
                logger.info('nothing to process in request')
            case Failure(ExpectedError()) as e:
                m = e.get_value().message
                logger.info(f'failed to process request: {m}')
                self.set_status(400, m)
            case _ as e:
                raise RuntimeError(f'unexpected storage result: {e}')

class StopHandler(RequestHandler):
    def initialize(self, queue: Queue[ProviderEvent]) -> None:
        self.queue = queue

    def post(self) -> None:
        self.queue.put_nowait(StopEvent())
        self.write('Goodbye.')

async def amain(debug: bool) -> None:
    config = Config.read_from_repo()

    queue = Queue[ProviderEvent]()
    match config.app.provider:
        case 'github':
            webhook = GithubWebhook(queue)
        case _:
            raise RuntimeError(f'unexpected provider: {config.app.provider}')
    if config.app.hmac:
        logger.info('HMAC secret provided, incoming requests will be verified')
    app = Application([
        ('/', MainHandler),
        ('/webhook', WebhookHandler, dict(
            token=config.app.hmac, webhook=webhook, debug=debug
        )),
        *([('/stop', StopHandler, dict(queue=queue))] if debug else []),
    ], debug=debug)
    app.listen(config.app.port)
    logger.info(f'serving on port {config.app.port}')
    async for event in queue:
        await IOLoop.current().run_in_executor(None, process, event)
        if type(event) is StopEvent:
            return
    IOLoop.current().stop()
    logger.info('done with the que')


def process(event: ProviderEvent) -> None:
    logger.info(f'ma, look, event! {event}')


def _main() -> None:
    main(parse_args())


if __name__ == '__main__':
    _main()
