import hashlib
import hmac
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Literal, cast

from meiga import Result, Error, Failure, Success
from tornado.escape import json_decode
from tornado.httputil import HTTPServerRequest
from tornado.queues import Queue

logger = getLogger(__name__)


class ExpectedError(Error):
    def __init__(self, message: str):
        self.message = message


class Webhook:
    def verify_request(self, token: bytes|None, request: HTTPServerRequest) \
            -> Result[Literal[True], ExpectedError]:
        raise NotImplementedError()

    def store_request(self, request: HTTPServerRequest) -> Result[bool, ExpectedError]:
        raise NotImplementedError()


class GithubWebhook(Webhook):
    def __init__(self, queue: Queue['ProviderEvent']) -> None:
        super().__init__()
        self.queue = queue

    def verify_request(self, token: bytes|None, request: HTTPServerRequest) \
            -> Result[Literal[True], ExpectedError]:
        # nothing to verify if we don't have hmac signing key
        if not token:
            return Success(True)

        signature = cast(str, request.headers.get('x-hub-signature-256', ''))
        if not signature:
            logger.info('header "x-hub-signature-256" missing in request')
            return Failure(ExpectedError('header "x-hub-signature-256" missing'))

        hash_object = hmac.new(token, msg=request.body, digestmod=hashlib.sha256)
        expected_signature = 'sha256=' + hash_object.hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            logger.info('header "x-hub-signature-256" in request does not match its body')
            return Failure(ExpectedError('header "x-hub-signature-256" does not match its body'))

        return Success(True)

    def store_request(self, request: HTTPServerRequest) -> Result[bool, ExpectedError]:
        logger.info('processing payload...')
        try:
            j = json_decode(request.body)
        except Exception as e:
            logger.warning(f'Failed to decode JSON from request body: {e}')
            return Failure(ExpectedError(f'Failed to decode JSON from request body: {e}'))
        event: ProviderEvent

        if is_created_pr_comment(j):
            logger.info(f'this is PR comment - {j["comment"]["html_url"]}')
            event = PrCommentEvent(
                pr=j['issue']['number'],
                message=j["comment"]["body"],
            )
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        if is_completed_workflow(j):
            logger.info(f'this is completed workflow - {j["workflow_run"]["html_url"]}')
            event = CheckCompletedEvent(
                commit=j['workflow_run']['head_sha']
            )
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        if is_ping_event(j):
            logger.info('this is ping event from terminal')
            event = PingEvent()
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        return Success(False)

def is_created_pr_comment(j: dict[str, Any]) -> bool:
    return (
        j.get('action') == 'created'
        and 'pull_request' in j.get('issue', dict())
        and 'comment' in j
    )

def is_completed_workflow(j: dict[str, Any]) -> bool:
    return (
        j.get('action') == 'completed'
        and 'workflow_run' in j
    )
    # shall be checked by
    # r = get('/repos/{owner}/{repo}/commits/{ref}/check-suites)
    # all(x['conclusion'] == 'success' for x in r.json()['check_suites'])

def is_ping_event(j: dict[str, Any]) -> bool:
    return j.get('ping') is True

class ProviderEvent():
    pass

@dataclass
class InitializeEvent(ProviderEvent):
    pass

@dataclass
class PingEvent(ProviderEvent):
    pass

@dataclass
class StopEvent(ProviderEvent):
    pass

@dataclass
class PrCommentEvent(ProviderEvent):
    pr: int
    message: str

@dataclass
class CheckCompletedEvent(ProviderEvent):
    commit: str
