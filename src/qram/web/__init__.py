import abc
import hashlib
import hmac
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any, Literal, cast

from meiga import Error, Failure, Result, Success
from tornado.escape import json_decode
from tornado.httputil import HTTPServerRequest
from tornado.queues import Queue

from qram.web.provider.github import Github


logger = getLogger(__name__)

EventQueue = Queue['QramEvent']


class ExpectedError(Error):
    def __init__(self, message: str):
        self.message = message


class Webhook:
    '''Subclasses transform incoming JSON requests into events for queue'''
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def verify_request(self, token: bytes|None, request: HTTPServerRequest) \
            -> Result[Literal[True], ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def store_request(self, request: HTTPServerRequest) -> Result[bool, ExpectedError]:
        raise NotImplementedError


class EventHandler:
    '''Subclasses perform provider-specific actions upon events from queue'''
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def handle_initialization(self) -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_stop(self) -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_pr_comment(self, event: 'PrCommentEvent') -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_check_complete(self, event: 'CheckCompletedEvent') -> Result[bool, ExpectedError]:
        raise NotImplementedError


class GithubWebhook(Webhook):
    def __init__(self, queue: EventQueue) -> None:
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
        except Exception as e: # noqa: BLE001
            logger.warning(f'Failed to decode JSON from request body: {e}')
            return Failure(ExpectedError(f'Failed to decode JSON from request body: {e}'))
        event: QramEvent

        if is_created_pr_comment(j):
            c = j['comment']
            logger.info(f'this is PR comment - {c["html_url"]}')
            event = PrCommentEvent(
                repo=j['repository']['full_name'],
                pr=j['issue']['number'],
                number=j['comment']['id'],
                message=j['comment']['body'],
            ).caused_by(f'WEB/webhook PR comment {c["id"]}')
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        # FIXME: is completed check
        if is_completed_workflow(j):
            wfr = j['workflow_run']
            logger.info(f'this is completed workflow - {wfr["html_url"]}')
            event = CheckCompletedEvent(
                repo=j['repository']['full_name'],
                commit=j['workflow_run']['head_sha'],
            ).caused_by(f'WEB/webhook WORKFLOW {wfr["id"]}')
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        if is_ping_event(j):
            logger.info('this is ping event from terminal')
            event = PingEvent().caused_by('WEB/webhook PING')
            self.queue.put_nowait(event)
            logger.info(f'enqueued: {event}')
            return Success(True)

        return Success(False)


class GithubHandler(EventHandler):
    api: Github

    def __init__(self, api: Github) -> None:
        self.api = api


    def handle_initialization(self) -> Result[bool, ExpectedError]:
        logger.info('This may take awhile...')
        import time
        time.sleep(1)
        return Success(True)


    def handle_stop(self) -> Result[bool, ExpectedError]:
        logger.info('some day...')
        return Success(True)


    def handle_pr_comment(self, event: 'PrCommentEvent') -> Result[bool, ExpectedError]:
        owner_repo = event.repo
        assert '/' in owner_repo
        comment_id = event.number

        logger.info(f'reacting "🚀" to comment {comment_id} in {owner_repo}')
        r = self.api.post(
            f'/repos/{owner_repo}/issues/comments/{comment_id}/reactions',
            json=dict(content='rocket'),
        )
        if not r.ok:
            msg = f'reaction to comment failed:\n{r.content.decode()}'
            logger.error(msg)
            return Failure(ExpectedError(msg))
        logger.info('done')
        # FIXME: process current command and enqueue PR
        return Success(True)


    def handle_check_complete(self, event: 'CheckCompletedEvent') -> Result[bool, ExpectedError]:
        logger.info('some day...')
        return Success(True)


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
    # : r = get('/repos/{owner}/{repo}/commits/{ref}/check-suites)
    # : all(x['conclusion'] == 'success' for x in r.json()['check_suites'])

def is_ping_event(j: dict[str, Any]) -> bool:
    return j.get('ping') is True


def is_check_completed(j: dict[str, Any]) -> bool:
    # FIXME: find out what checks look like
    return False


_event_id = 1
@dataclass
class QramEvent:
    event_id: int = field(init=False)
    cause: str = field(init=False)
    def __post_init__(self) -> None:
        global _event_id
        self.event_id = _event_id
        self.cause = ''
        _event_id += 1

    def caused_by(self, explanation: str) -> 'QramEvent':
        self.cause = explanation
        return self

@dataclass
class ProviderEvent(QramEvent):
    repo: str

@dataclass
class InitializeEvent(QramEvent):
    pass

@dataclass
class PingEvent(QramEvent):
    pass

@dataclass
class StopEvent(QramEvent):
    pass

@dataclass
class PrCommentEvent(ProviderEvent):
    number: int
    pr: int
    message: str

@dataclass
class CheckCompletedEvent(ProviderEvent):
    commit: str
