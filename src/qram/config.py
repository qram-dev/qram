import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, StrictStr, model_validator

logger = logging.getLogger(__name__)

# TODO: consider using pydantic_settings instead of manual env parsing


class AppConfig(BaseModel, extra='forbid'):
    bind_to: StrictStr
    port: int
    cors_origin: StrictStr
    github: CfgGithub | None

    @staticmethod
    def config_from_env() -> AppConfig:
        payload: dict[str, Any] = dict()
        payload['bind_to'] = os.environ.get('QRAM_BIND_TO', '127.0.0.1')
        payload['port'] = int(os.environ.get('QRAM_PORT', '7890'))
        payload['cors_origin'] = os.environ.get('QRAM_CORS_ORIGIN', '')

        provider = _envvar('QRAM_PROVIDER')
        if provider == 'github':
            pem = _file_fallback('QRAM_GITHUB_PEM', 'QRAM_GITHUB_PEM_FILE')
            hmac = _file_fallback('QRAM_GITHUB_HMAC', 'QRAM_GITHUB_HMAC_FILE')

            payload['github'] = dict(
                app_id=_envvar('QRAM_GITHUB_APP_ID'),
                installation_id=_envvar('QRAM_GITHUB_INSTALLATION_ID'),
                pem=pem,
                hmac=hmac,
            )
        else:
            msg = f'unsupported provider: {provider}'
            raise RuntimeError(msg)

        return AppConfig.model_validate(payload)

    # looks silly; hopefully will make more sense when not only github is supported
    @model_validator(mode='after')
    def ensure_provider(self) -> AppConfig:
        if not self.github:
            msg = 'no provider configured in AppConfig'
            raise ValueError(msg)
        return self


class CfgGithub(BaseModel, extra='forbid'):
    app_id: StrictStr
    installation_id: StrictStr
    pem: StrictStr
    hmac: StrictStr


def _envvar(var: str) -> str:
    v = os.environ.get(var)
    if v is None:
        msg = f'missing required env var: {var}'
        raise RuntimeError(msg)
    return v


def _file_fallback(value_env: str, file_env: str) -> str:
    value = os.environ.get(value_env)
    if value:
        return value
    logger.info(f'envvar {value_env} not set; fallback to {file_env}')
    p = Path(_envvar(file_env))
    logger.info(f'reading from file {p}')
    if not p or not p.is_file():
        msg = f'invalid file: {p.absolute()}'
        raise ValueError(msg)
    c = p.read_text().strip()
    if not c:
        msg = f'file is empty: {p.absolute()}'
        raise ValueError(msg)
    return c
