import abc
from typing import Literal

from meiga import Result
from tornado.httputil import HTTPServerRequest

from qram.errors import ExpectedError
from qram.web.events import CheckCompletedEvent, PrCommentEvent


class Webhook:
    """Subclasses transform incoming JSON requests into events for queue"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def verify_request(
        self, token: bytes | None, request: HTTPServerRequest
    ) -> Result[Literal[True], ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def store_request(self, request: HTTPServerRequest) -> Result[bool, ExpectedError]:
        raise NotImplementedError


class EventHandler:
    """Subclasses perform provider-specific actions upon events from queue"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def handle_initialization(self) -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_stop(self) -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_pr_comment(self, event: PrCommentEvent) -> Result[bool, ExpectedError]:
        raise NotImplementedError

    @abc.abstractmethod
    def handle_check_complete(self, event: CheckCompletedEvent) -> Result[bool, ExpectedError]:
        raise NotImplementedError
