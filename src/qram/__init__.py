import re

from itertools import takewhile
from typing import Callable, Iterable, List, Tuple, TypeVar

from jinja2 import Environment

from qram import git
from qram.config import Config
from qram.formatter import PrFormatter
from qram.web.provider import Pr

CommitAndBranches = Tuple[git.Hash, List[str]]


def format_merge_message(pr: Pr, config: Config) -> str:
    e = Environment()
    return e.from_string(
        source=config.merge_template.jinja,
        globals=dict(
            pr=pr,
            cfg=config
        )
    ).render().strip()


def format_author(pr: Pr) -> str:
    username = pr.author["username"]
    author_id = pr.author['id']
    email = f'{username}@users.noreply.github.com'
    if author_id:
        email = f'{author_id}+{email}'
    return f'{username} <{email}>'


def collect_staging(staging_branch: str, target_branch: str) -> Iterable[CommitAndBranches]:
    log = git.log(staging_branch)
    queue = takewhile(lambda tpl: target_branch not in tpl[1], log)
    for hash, branches in queue:
        if any(
            b.endswith(PrFormatter.POSTFIX_MERGE)
            for b in branches
        ):
            yield hash, branches


def extract_pr_from_merge(branch: str, config: Config) -> int:
    prefix = config.branching.branch_folder
    postfix = PrFormatter.POSTFIX_MERGE
    REGEX = re.compile(f'{prefix}/pr(\\d+)/({postfix})')
    m = REGEX.search(branch)
    assert m is not None, f'string {branch} does not match regex'
    return int(m.group(1))


def extract_pr_from_branch_list(branches: List[str], config: Config) -> int:
    for b in branches:
        if b.endswith(PrFormatter.POSTFIX_MERGE):
            return extract_pr_from_merge(b, config)
    raise RuntimeError(f'No merge postfix among branches: {branches}')


T = TypeVar('T')
def takewhile_inclusive(predicate: Callable[[T], bool], iterable: Iterable[T]) -> Iterable[T]:
    for x in iterable:
        yield x
        if predicate(x):
            break
