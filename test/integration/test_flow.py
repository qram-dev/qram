from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture
from pytest_bdd import scenarios, given, when, then, parsers

from qram import flow, git
from qram.config import Config
from qram.formatter import BranchFormatter
from qram.github import Pr

from test.integration.mocks import GithubMock
from .. import chdir


scenarios('scenarios/successful-flow.gherkin')


class Context(SimpleNamespace):
    config: Config
    branches: BranchFormatter
    gh: GithubMock
    pr: Pr
    pr_branch_original_hash: str
    branch_rebased: str
    source: str


@pytest.fixture()
def context(repo_tar: Path, mocker: MockerFixture) -> Context:
    mocker.patch('qram.git.push')
    cd = chdir(repo_tar)
    cd.__enter__()
    cfg = Config()
    return Context(
        config = cfg,
        branches = BranchFormatter(cfg),
        gh = GithubMock(),
        cd = cd,
    )

@given(parsers.parse('PR {num:d} exists'))
def bdd1ff841b74b(context: Context, num: int) -> None:
    context.pr = context.gh.get_pr(num)
    context.pr_branch_original_hash = git.hash_of(context.pr.branch_head)


@when('Flow starts')
def bdd966edddf2f(context: Context) -> None:
    pass


@then('No markers exist except PR branch')
def bdd9206dec454(context: Context) -> None:
    branches_pr = context.branches.pr(context.pr.number)
    context.all_branches_of_pr = [
        branches_pr.rebase_target, branches_pr.bad, branches_pr.source, branches_pr.merge,
    ]
    for branch in context.all_branches_of_pr:
        assert not git.branch_exists(branch)


@when(parsers.parse('PR {num:d} is enqueued'))
def bdde2edbfedc7(context: Context, num: int) -> None:
    flow.prepare(1, context.gh, context.config)
    context.branch_rebased = git.hash_of(context.pr.branch_head)
    context.source = git.hash_of(context.branches.pr(context.pr.number).source)


@then(parsers.parse('Push was called {cnt:d} time'))
@then(parsers.parse('Push was called {cnt:d} times'))
def bdd466fdfb405(cnt: int) -> None:
    assert git.push.call_count == cnt
    git.push.call_count = 0


@then('Some new markers appear')
def bdd57fb5d36b7(context: Context) -> None:
    branches_pr = context.branches.pr(context.pr.number)
    assert git.branch_exists(branches_pr.rebase_target)
    assert not git.branch_exists(branches_pr.bad)
    assert git.branch_exists(branches_pr.source)
    assert git.branch_exists(branches_pr.merge)


@then('Source and rebase match original branch')
def bdd2fe4ed68e1(context: Context) -> None:
    source = git.hash_of(context.branches.pr(context.pr.number).source)
    assert source == context.pr_branch_original_hash
    branch_rebased = git.hash_of(context.pr.branch_head)
    assert branch_rebased == context.pr_branch_original_hash


@then('Merge-after-rebase matches new queue head')
def bdd5efc04868c(context: Context) -> None:
    queue = context.branches.queue
    merge = context.branches.pr(context.pr.number).merge
    assert git.hash_of(merge) == git.hash_of(queue)


@then('Main does not match queue')
def bddefbb73f51d(context: Context) -> None:
    queue = context.branches.queue
    target = context.branches.target
    assert git.hash_of(target) != git.hash_of(queue)


@when(parsers.parse('PR {num:d} is merged'))
def bdd0cdc37c32f(context: Context, num: int) -> None:
    flow.merge(num, context.gh, context.config)


@then('Markers disappear together with original branch')
def bdd137d073088(context: Context) -> None:
    for branch in [*context.all_branches_of_pr, context.pr.branch_head]:
        assert not git.branch_exists(branch)


@then('Main now matches queue')
def bdda23d20c9bb(context: Context) -> None:
    queue = context.branches.queue
    target = context.branches.target
    assert git.hash_of(target) == git.hash_of(queue)
