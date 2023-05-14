import logging

from meiga import Failure, Success
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler

from qram import web
from qram.config import Config
from qram.web import EventHandler, EventQueue, ExpectedError, GithubHandler, GithubWebhook, Webhook
from qram.web.provider.github import github_api


logger = logging.getLogger(__name__)


# pylance has issues understanding inheritance in tornado
#   pyright: reportIncompatibleMethodOverride=false


class MainHandler(RequestHandler):
    def get(self) -> None:
        self.write('qram')


class WebhookHandler(RequestHandler):
    webhook: Webhook
    debug: bool

    def initialize(self, token: str|None, webhook: Webhook, debug: bool) -> None: # noqa: FBT001
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
    def initialize(self, queue: EventQueue) -> None:
        self.queue = queue

    def post(self) -> None:
        self.queue.put_nowait(web.StopEvent().caused_by('WEB/stop'))
        self.write('Goodbye.')


async def make_server(config: Config, *, debug: bool, provide_stop: bool,
                      initialize_repos: bool) -> None:
    if config.app.hmac:
        logger.info('HMAC secret provided, incoming requests will be verified')
    queue = EventQueue()
    await queue.put(web.PingEvent().caused_by('initialization'))
    if initialize_repos:
        await queue.put(web.InitializeEvent().caused_by('initialization'))

    match config.app.provider:
        case 'github':
            assert config.app.github is not None
            logger.info( '    PROVIDER: GITHUB')
            logger.info(f'         APP: {config.app.github.app_id}')
            logger.info(f'INSTALLATION: {config.app.github.installation_id}')
            webhook = GithubWebhook(queue)
            handler = GithubHandler(github_api(config))
        case _:
            raise RuntimeError(f'unexpected provider: {config.app.provider}')

    app = Application([
        ('/', MainHandler),
        ('/webhook', WebhookHandler, dict(
            token=config.app.hmac, webhook=webhook, debug=debug,
        )),
        *([('/stop', StopHandler, dict(queue=queue))] if provide_stop else []),
    ], debug=debug)

    app.listen(config.app.port)
    logger.info(f'serving on port {config.app.port}')

    async for event in queue:
        await IOLoop.current().run_in_executor(None, process, event, handler)
        if isinstance(event, web.StopEvent):
            break
        logger.debug('next event...')
    logger.info('done with the que')


def process(event: web.QramEvent, handler: EventHandler) -> None:
    logger.debug(f'processing event {event}')
    match event:
        case web.InitializeEvent():
            logger.info('Initializing available repos')
            match handler.handle_initialization():
                case Success(True):
                    logger.info('Initialization done')
                case _ as e:
                    logger.critical(f'❗ Initialization failed: {e}')
                    return
        case web.StopEvent():
            logger.info('Requested to stop; Qram will now exit')
            handler.handle_stop()
        case web.PingEvent():
            logger.info('Pong!')
        case web.PrCommentEvent() as e:
            logger.info(f'A comment was posted on PR #{e.pr}')
            if event.message.strip().startswith('!qram'):
                logger.info('It is meant for us!')
                handler.handle_pr_comment(e)
            else:
                logger.info('It is just some comment')
        case web.CheckCompletedEvent() as e:
            logger.info(f'A check completed on {e.commit}!')
            handler.handle_check_complete(e)
        case _ as e:
            logger.warning(f'⚠️ Unexpected event type {e}\nIt is most likely a bug in Qram')
