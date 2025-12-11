import logging

from qram.config import AppConfig
from qram.web.github import GithubApi

logger = logging.getLogger(__name__)


def reconfigure_github_webhook(url: str, cfg: AppConfig) -> None:
    if not cfg.github:
        logger.warning('GitHub config not found, skipping webhook reconfiguration')
        return

    gh = cfg.github
    msg = f'github: app={gh.app_id} installation={gh.installation_id}: set webhook to {url}'
    if gh.hmac:
        msg += ' (with HMAC secret)'
    logger.info(msg)

    payload = dict(
        url=url,
        content_type='json',
        secret=gh.hmac,
    )
    api = GithubApi(cfg)
    r = api.http_patch('app/hook/config', json=payload, use_jwt=True)
    if not r.is_success:
        msg = f'Failed to reconfigure webhook: {r.content.decode()}'
        raise RuntimeError(msg)

    logger.info('webhook reconfigured')
