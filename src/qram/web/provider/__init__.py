import abc
from dataclasses import dataclass


class ProviderApi:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def repo(self, owner: str, repo: str) -> 'ProviderRepoApi':
        raise NotImplementedError()


class ProviderRepoApi:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_pr(self, pr: int) -> 'Pr':
        raise NotImplementedError()


@dataclass
class Pr:
    number: int
    title: str
    body: str | None
    branch_head: str
    author: dict[str, str | int | None]
