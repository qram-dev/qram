from itertools import takewhile
from typing import Iterable, List, Optional, Tuple

from jinja2 import Environment

import qram.git as git
from qram.config import Config
from qram.formatter import PrFormatter
from qram.github import Pr

CommitAndBranches = Tuple[str, List[str]]


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


def find_merges_before(ref: str, target_branch: str, *, include_target_branch: bool=False) -> List[CommitAndBranches]:
    log = _get_log(f'{ref}^')
    log_after_main = takewhile(lambda tpl: target_branch not in tpl[1], log)
    merges_in_log = _extract_merges(log_after_main, target_branch if include_target_branch else None)
    return list(merges_in_log)


def find_merges_after(ref: str, queue_branch: str) -> List[CommitAndBranches]:
    log = _get_log(queue_branch)
    log_after_ref = takewhile(lambda tpl: ref not in tpl[1], log)
    merges_in_log = _extract_merges(log_after_ref)
    # we iterated log from newest to oldest above - but better rebase branches in order they were merged
    return list(reversed(list(merges_in_log)))


def _get_log(head: str) -> Iterable[Tuple[str, List[str]]]:
    SEP = ' - '
    log = git.check_output(['log', f'--format=format:%h{SEP}%D', f'{head}']).splitlines()
    splits = (tuple(line.split(SEP)) for line in log)
    for hash, branches_line in splits:
        branches = git.extract_branches_from_line(branches_line)
        if branches:
            yield hash, branches

def _extract_merges(log: Iterable[Tuple[str, List[str]]], with_branch: Optional[str]=None) -> Iterable[CommitAndBranches]:
    """Get all commit+branch pairs where branch is a merge marker. If `with_target_branch` is specified,
        check also whether branch is the `main` branch to which merges are directed.
    """
    for hash, branches in log:
        has_merges = any(b for b in branches if b.endswith(PrFormatter.MERGE_POSTFIX))
        if has_merges or (with_branch and with_branch in branches):
            yield hash, branches
