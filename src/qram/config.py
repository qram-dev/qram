import logging
import os
from typing import Any

from pydantic import BaseModel, StrictStr

logger = logging.getLogger(__name__)

# TODO: consider using pydantic_settings instead of manual env parsing


class AppConfig(BaseModel, extra='forbid'):
    bind_to: StrictStr
    port: int

    @staticmethod
    def config_from_env() -> AppConfig:
        payload: dict[str, Any] = dict()
        payload['bind_to'] = os.environ.get('QRAM_BIND_TO', '127.0.0.1')
        payload['port'] = int(os.environ.get('QRAM_PORT', '7890'))
        return AppConfig.model_validate(payload)
