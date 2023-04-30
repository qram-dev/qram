import re

from functools import cache
from typing import List

from qram.config import Config

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
    POSTFIX_MERGE = 'merge-after-rebase'
    POSTFIX_BAD = 'bad'
    POSTFIX_GOOD = 'good'
    POSTFIX_REBASe = 'rebase-target'
    POSTFIX_SOURCE = 'source'
    rebase: str
    merge: str
    source: str
    bad: str
    _config: Config

    def __init__(self, pr: int, config: Config) -> None:
        self._config = config
        self.rebase = f'{config.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_REBASe}'
        self.merge = f'{config.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_MERGE}'
        self.source = f'{config.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_SOURCE}'
        self.bad = f'{config.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_BAD}'
        self.good = f'{config.branch_folder}/pr{pr}/{PrFormatter.POSTFIX_GOOD}'

    @staticmethod
    def extract_pr_from_branch(branch: str, config: Config) -> int:
        prefix = config.branch_folder
        postfix = '|'.join([
            PrFormatter.POSTFIX_MERGE, PrFormatter.POSTFIX_BAD,
            PrFormatter.POSTFIX_REBASe, PrFormatter.POSTFIX_SOURCE
        ])
        REGEX = re.compile(f'{prefix}/pr(\\d+)/({postfix})')
        m = REGEX.search(branch)
        assert m is not None, f'string {branch} does not match regex'
        return int(m.group(1))

    @staticmethod
    def extract_pr_from_branch_list(branches: List[str], config: Config) -> int:
        postfixes = [
            PrFormatter.POSTFIX_MERGE, PrFormatter.POSTFIX_BAD,
            PrFormatter.POSTFIX_REBASe, PrFormatter.POSTFIX_SOURCE
        ]
        for b in branches:
            for p in postfixes:
                if b.endswith(p):
                    return PrFormatter.extract_pr_from_branch(b, config)
        raise RuntimeError(f'No valid postfix among branches: {branches}')
