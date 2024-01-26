from functools import cache

from qram.config import RepoConfig


class BranchFormatter:
    _config: RepoConfig
    queue: str
    target: str

    def __init__(self, config: RepoConfig) -> None:
        self._config = config
        self.queue = f'{self._config.branching.branch_folder}/queue'
        self.target = config.branching.target_branch

    @cache
    def pr(self, pr: int) -> 'PrFormatter':
        return PrFormatter(pr, self._config)

class PrFormatter:
    POSTFIX_MERGE = 'merge-after-rebase'
    POSTFIX_BAD = 'bad'
    POSTFIX_GOOD = 'good'
    POSTFIX_REBASe = 'rebase-target'
    POSTFIX_SOURCE = 'source'
    rebase: str
    merge: str
    source: str
    bad: str
    _config: RepoConfig

    def __init__(self, pr: int, config: RepoConfig) -> None:
        self._config = config
        self.rebase = f'{config.branching.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_REBASe}'
        self.merge = f'{config.branching.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_MERGE}'
        self.source = f'{config.branching.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_SOURCE}'
        self.bad = f'{config.branching.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_BAD}'
        self.good = f'{config.branching.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_GOOD}'
