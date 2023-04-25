from qram.config import Config
from functools import cache

class BranchFormatter:
    _config: Config
    queue: str
    target: str

    def __init__(self, config: Config) -> None:
        self._config = config
        self.queue = f'{self._config.branch_folder}/queue'
        self.target = config.target_branch

    @cache
    def pr(self, pr: int) -> 'PrFormatter':
        return PrFormatter(pr, self._config)

class PrFormatter:
    rebase_target: str
    merge: str
    source: str

    def __init__(self, pr: int, config: Config) -> None:
        self.rebase_target = f'{config.branch_folder}/pr{pr}/rebase-target'
        self.merge = f'{config.branch_folder}/pr{pr}/merge-after-rebase'
        self.source = f'{config.branch_folder}/pr{pr}/source'
