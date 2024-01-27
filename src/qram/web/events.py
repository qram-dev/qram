from dataclasses import dataclass, field

from tornado.queues import Queue

from qram.types import Hash


EventQueue = Queue['QramEvent']


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
class RepoEvent(QramEvent):
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
class PrCommentEvent(RepoEvent):
    number: int
    pr: int
    message: str


@dataclass
class CheckCompletedEvent(RepoEvent):
    commit: Hash
    good: bool
