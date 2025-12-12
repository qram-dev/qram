import uvicorn
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from qram.config import AppConfig
from qram.web import WebhookHandlerBase
from qram.web.github import GithubWebhookHandler

router = APIRouter()


@router.get('/ping')
async def ping() -> JSONResponse:
    return JSONResponse(status_code=200, content=dict(ping='pong'))


# respond to preflight CORS or other checks
@router.options('/webhook')
async def webhook_options(request: Request) -> Response:
    cfg = request.app.state.config
    handler = get_webhook_handler(cfg)
    headers = handler.get_cors_headers()
    return Response(status_code=200, headers=headers)


@router.post('/webhook')
async def webhook(request: Request) -> JSONResponse:
    handler = get_webhook_handler(request.app.state.config)
    return await handler.handle(request)


# TODO: should be stored in app.state?
def get_webhook_handler(cfg: AppConfig) -> WebhookHandlerBase:
    if cfg.github:
        return GithubWebhookHandler(cfg)
    msg = 'no known provider in config'
    raise NotImplementedError(msg)


def create_app(cfg: AppConfig) -> FastAPI:
    app = FastAPI()
    app.state.config = cfg
    app.include_router(router)
    return app


def run_app(app: FastAPI, config: AppConfig, *, debug: bool = False) -> None:
    uvicorn.run(
        app,
        host=config.bind_to,
        port=config.port,
        log_level='debug' if debug else None,
    )
