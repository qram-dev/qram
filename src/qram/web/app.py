import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from qram.config import AppConfig

router = APIRouter()


@router.get('/ping')
async def ping() -> JSONResponse:
    return JSONResponse(status_code=200, content=dict(ping='pong'))


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
