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
    MERGE_POSTFIX = 'merge-after-rebase'
    BAD_POSTFIX = 'bad'
    REBASE_TARGET_POSTFIX = 'rebase-target'
    SOURCE_POSTFIX = 'source'
    rebase_target: str
    merge: str
    source: str
    bad: str
    _config: Config

    def __init__(self, pr: int, config: Config) -> None:
        self._config = config
        self.rebase_target = f'{config.branch_folder}/pr{pr}/{PrFormatter.REBASE_TARGET_POSTFIX}'
        self.merge = f'{config.branch_folder}/pr{pr}/{PrFormatter.MERGE_POSTFIX}'
        self.source = f'{config.branch_folder}/pr{pr}/{PrFormatter.SOURCE_POSTFIX}'
        self.bad = f'{config.branch_folder}/pr{pr}/{PrFormatter.BAD_POSTFIX}'

    @staticmethod
    def extract_pr_from_branch(branch: str, config: Config) -> int:
        prefix = config.branch_folder
        postfix = '|'.join([
            PrFormatter.MERGE_POSTFIX, PrFormatter.BAD_POSTFIX,
            PrFormatter.REBASE_TARGET_POSTFIX, PrFormatter.SOURCE_POSTFIX
        ])
        REGEX = re.compile(f'{prefix}/pr(\\d+)/({postfix})')
        m = REGEX.search(branch)
        assert m is not None, f'string {branch} does not match regex'
        return int(m.group(1))

    @staticmethod
    def extract_pr_from_branch_list(branches: List[str], config: Config) -> int:
        postfixes = [
            PrFormatter.MERGE_POSTFIX, PrFormatter.BAD_POSTFIX,
            PrFormatter.REBASE_TARGET_POSTFIX, PrFormatter.SOURCE_POSTFIX
        ]
        for b in branches:
            for p in postfixes:
                if b.endswith(p):
                    return PrFormatter.extract_pr_from_branch(b, config)
        raise RuntimeError(f'No valid postfix among branches: {branches}')
