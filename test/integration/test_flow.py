from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from pytest_bdd import scenarios, given, when, then, parsers

from qram import flow, git
from qram.config import Config
from qram.formatter import BranchFormatter
from qram.github import Pr
from test.integration import DataTable, datatable, str2bool

from test.integration.mocks import GithubMock
from .. import chdir


scenarios('scenarios/successful-flow.gherkin')


class PrInfo:
    object: Pr
    original: git.Hash
    'original commit where PR branch was pointing'
    rebased: git.Hash
    'new commit where PR branch is pointing after rebase'

    def __init__(self, object: Pr, original: git.Hash) -> None:
        self.object = object
        self.original = original

class Context(SimpleNamespace):
    config: Config
    branches: BranchFormatter
    gh: GithubMock
    pr: dict[int, PrInfo]


### fixtures


@pytest.fixture()
def mocked_git_push(mocker: MockerFixture) -> MagicMock:
    return mocker.patch('qram.git.push')


@pytest.fixture()
def context(repo_tar: Path) -> Context:
    cd = chdir(repo_tar)
    cd.__enter__()
    cfg = Config()
    return Context(
        config = cfg,
        branches = BranchFormatter(cfg),
        gh = GithubMock(),
        cd = cd,
        pr = dict(),
    )


### bdd


@given(parsers.parse("PR '{num:d}' exists"))
def _(context: Context, num: int) -> None:
    p = context.gh.get_pr(num)
    context.pr[num] = PrInfo(
        object = p,
        original = git.hash_of(p.branch_head)
    )


@when('Flow starts')
def _(context: Context, mocked_git_push: MagicMock) -> None:
    mocked_git_push.call_count = 0


@then(parsers.parse("Markers state is:\n{markers:T}", extra_types={'T': datatable(int, str, str2bool)}))
def _(context: Context, markers: DataTable[int, str, bool]) -> None:
    for pr, marker, state in markers:
        marker = translate_alias(marker, context.branches, context.pr[pr])
        assert git.branch_exists(marker) == state


# despite `@given`, this step does not setup anything in the scenario itself, it is used only for
# better flowing sentences
@given(parsers.parse("PR '{num:d}':"), target_fixture='observed_pr')
def _(context: Context, num: int) -> int:
    return num


@when(parsers.parse("PR '{num:d}' is enqueued"))
@given(parsers.parse("PR '{num:d}' was enqueued"))
def _(context: Context, mocked_git_push: MagicMock, num: int) -> None:
    flow.prepare(num, context.gh, context.config)
    pr = context.pr[num]
    pr.rebased = git.hash_of(pr.object.branch_head)


@then(parsers.parse("Push was called '{cnt:d}' time"))
@then(parsers.parse("Push was called '{cnt:d}' times"))
def _(cnt: int, mocked_git_push: MagicMock) -> None:
    assert mocked_git_push.call_count == cnt
    mocked_git_push.call_count = 0


@then(parsers.parse("- its marker '{first}' {state} its {second} commit"))
@then(parsers.parse("- its marker '{first}' {state} its {second} commit{}"))
@then(parsers.parse("- its marker '{first}' {state} branch '{second}'"))
@then(parsers.parse("- its marker '{first}' {state} branch '{second}'{}"))
def _(context: Context, observed_pr: int, first: str, state: str, second: str) -> None:
    pr = context.pr[observed_pr]
    compare_aliases(context, pr, first, state, second)


@then(parsers.parse("Branch '{first}' {state} branch '{second}' {}"))
@then(parsers.parse("Branch '{first}' {state} branch '{second}'"))
def _(context: Context, first: str, state: str, second: str) -> None:
    compare_aliases(context, None, first, state, second)


@when(parsers.parse("PR '{num:d}' is merged"))
@given(parsers.parse("PR '{num:d}' was merged"))
def _(context: Context, num: int) -> None:
    flow.merge(num, context.gh, context.config)

@then(parsers.parse("PR '{num:d}' cannot be merged yet"))
def _(context: Context, num: int) -> None:
    with pytest.raises(Exception):
        flow.merge(num, context.gh, context.config)


### utils


def compare_aliases(context: Context, pr: Optional[PrInfo], first: str, state: str, second: str) -> None:
    what_is = calculate_hash(first, context.branches, pr)
    should_be = calculate_hash(second, context.branches, pr)
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
    if alias_from_datatable in ('rebase', 'source', 'merge', 'bad'):
        markers = global_branches.pr(pr.object.number)
        marker = markers.__getattribute__(alias_from_datatable)
        assert type(marker) is str
        return marker
    raise ValueError(f'Unknown reference: {alias_from_datatable}')


def calculate_hash(
        alias_from_datatable: str,
        global_branches: BranchFormatter,
        pr: Optional[PrInfo]=None
    ) -> git.Hash:
    branch = translate_alias(alias_from_datatable, global_branches, pr)
    return git.hash_of(branch)
