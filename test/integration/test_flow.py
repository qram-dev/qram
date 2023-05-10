import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Generator, Optional
from unittest.mock import MagicMock

import pytest
from pytest_bdd import scenarios, given, when, then, parsers

import qram.config
from qram import flow
from qram.git import Git, Hash
from qram.config import Config
from qram.formatter import BranchFormatter
from qram.web.provider.github import Pr
from test.integration import DataTable, datatable, str2bool

from test.integration.mocks import GithubMock


# these are under our protection
# pyright: reportPrivateUsage=false


scenarios('scenarios/successful-flow.gherkin')
scenarios('scenarios/bad-flow.gherkin')


class PrInfo:
    object: Pr
    original: Hash
    'original commit where PR branch was pointing'
    rebased: Hash
    'new commit where PR branch is pointing after rebase'

    def __init__(self, object: Pr, original: Hash) -> None:
        self.object = object
        self.original = original

class Context(SimpleNamespace):
    config: Config
    branches: BranchFormatter
    gh: GithubMock
    pr: dict[int, PrInfo]


### fixtures


@pytest.fixture()
def context(caplog: pytest.LogCaptureFixture) -> Generator[Context, None, None]:
    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(logging.Formatter(
        '{levelname:5} : {name:10} : {message}', style='{',
    ))
    cfg = qram.config._defaults
    yield Context(
        config = cfg,
        branches = BranchFormatter(cfg),
        gh = GithubMock(),
        pr = dict(),
    )


@pytest.fixture()
def git(repo_tar: Path) -> Git:
    g = Git(repo_tar)
    g.push = MagicMock()
    return g


### bdd


@given(parsers.parse("PR '{num:d}' exists"))
def _(context: Context, git: Git, num: int) -> None:
    p = context.gh.get_pr(num)
    context.pr[num] = PrInfo(
        object = p,
        original = git.hash_of(p.branch_head)
    )


@when('Flow starts')
def _(context: Context, git: Git) -> None:
    assert isinstance(git.push, MagicMock)
    git.push.call_count = 0


@then(parsers.parse("Markers state is:\n{markers:T}",
                    extra_types={'T': datatable(int, str, str2bool)}))
def _(context: Context, git: Git, markers: DataTable[int, str, bool]) -> None:
    for pr, marker, state in markers:
        marker = translate_alias(marker, context.branches, context.pr[pr])
        assert git.branch_exists(marker) == state


# despite `@given`, this step does not setup anything in the scenario itself, it is used only for
# better flowing sentences
@then(parsers.parse("For PR '{num:d}':"), target_fixture='observed_pr')
@given(parsers.parse("PR '{num:d}':"), target_fixture='observed_pr')
def _(context: Context, num: int) -> int:
    return num


@when(parsers.parse("PR '{num:d}' is enqueued"))
@given(parsers.parse("PR '{num:d}' was enqueued"))
def _(context: Context, git: Git, num: int) -> None:
    flow.prepare(git, num, context.gh, context.config)
    pr = context.pr[num]
    pr.rebased = git.hash_of(pr.object.branch_head)


@then(parsers.parse("Push was called '{cnt:d}' time"))
@then(parsers.parse("Push was called '{cnt:d}' times"))
def _(git: Git, cnt: int) -> None:
    assert isinstance(git.push, MagicMock)
    assert git.push.call_count == cnt
    git.push.call_count = 0


@then(parsers.parse("- its marker '{first}' {state} its {second} commit"))
@then(parsers.parse("- its marker '{first}' {state} its {second} commit{}"))
@then(parsers.parse("- its marker '{first}' {state} branch '{second}'"))
@then(parsers.parse("- its marker '{first}' {state} branch '{second}'{}"))
def _(context: Context, git: Git, observed_pr: int, first: str, state: str, second: str) -> None:
    pr = context.pr[observed_pr]
    compare_aliases(context, git, pr, first, state, second)


@then(parsers.parse("- it is on top of PR '{other:d}' {}"))
@then(parsers.parse("- it is on top of PR '{other:d}'"))
def _(context: Context, git: Git, observed_pr: int, other: int) -> None:
    above = context.branches.pr(observed_pr)
    below = context.branches.pr(other)
    assert git.hash_of(above.rebase) == git.hash_of(below.merge)


@then(parsers.parse("Branch '{first}' {state} branch '{second}' {}"))
@then(parsers.parse("Branch '{first}' {state} branch '{second}'"))
def _(context: Context, git: Git, first: str, state: str, second: str) -> None:
    compare_aliases(context, git, None, first, state, second)


@when(parsers.parse("Stage is shaken"))
@given(parsers.parse("Stage was shaken"))
def _(context: Context, git: Git) -> None:
    flow.shake_stage(git, context.gh, context.config)


@when(parsers.parse("PR '{num:d}' is marked '{state}'"))
@given(parsers.parse("PR '{num:d}' was marked '{state}'"))
def _(context: Context, git: Git, num: int, state: str) -> None:
    if state == 'good':
        ok = True
    elif state == 'bad':
        ok = False
    else:
        raise ValueError(f'Unknown state: `{state}`')
    merge_hash = calculate_hash(git, 'merge', context.branches, context.pr[num])
    flow.mark_merge(git, merge_hash, context.config, ok)


@then(parsers.parse("PR '{num:d}' cannot be merged yet"))
def _(context: Context, git: Git, num: int) -> None:
    with pytest.raises(Exception):
        flow._merge(git, num, context.gh, context.config)


### utils


def compare_aliases(context: Context, git: Git, pr: Optional[PrInfo],
                    first: str, state: str, second: str) -> None:
    what_is = calculate_hash(git, first, context.branches, pr)
    should_be = calculate_hash(git, second, context.branches, pr)
    if state == 'matches':
        assert what_is == should_be
    elif state == 'does not match':
        assert what_is != should_be
    else:
        raise ValueError(f'Unknown state: `{state}`')


def translate_alias(
        alias_from_datatable: str,
        global_branches: BranchFormatter,
        pr: Optional[PrInfo]=None
) -> str:
    if alias_from_datatable in ('target', 'queue'):
        branch = global_branches.__getattribute__(alias_from_datatable)
        assert type(branch) is str
        return branch
    if pr is None:
        raise ValueError(f'PR object must be present for `{alias_from_datatable}` reference')
    if alias_from_datatable == 'original':
        # while not a branch, it is still viable input for `hash_of()`
        return str(pr.original)
    if alias_from_datatable == 'head':
        return pr.object.branch_head
    if alias_from_datatable in ('rebase', 'source', 'merge', 'bad', 'good'):
        markers = global_branches.pr(pr.object.number)
        marker = markers.__getattribute__(alias_from_datatable)
        assert isinstance(marker, str)
        return marker
    raise ValueError(f'Unknown reference: {alias_from_datatable}')


def calculate_hash(
        git: Git,
        alias_from_datatable: str,
        global_branches: BranchFormatter,
        pr: Optional[PrInfo]=None
    ) -> Hash:
    branch = translate_alias(alias_from_datatable, global_branches, pr)
    return git.hash_of(branch)
