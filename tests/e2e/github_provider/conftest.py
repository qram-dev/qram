import logging
import os

import pytest
from dotenv import load_dotenv

from qram.config import AppConfig

from ..helpers import reconfigure_github_webhook

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session', autouse=True)
def configure_webhook() -> None:
    """
    Reconfigure the GitHub webhook before running e2e tests.
    """
    _ = load_dotenv()

    url = os.environ.get('QRAM_WEBHOOK_URL')
    if not url:
        logger.warning('QRAM_WEBHOOK_URL not set, skipping webhook reconfiguration')
        return

    cfg = AppConfig.config_from_env()
    reconfigure_github_webhook(url, cfg)
