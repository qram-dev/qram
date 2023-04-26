from pathlib import Path

from pytest_mock import MockerFixture

from qram import flow, git
from qram.config import Config
from qram.formatter import BranchFormatter
from qram.github import Pr

from test.integration.mocks import GithubMock
from .. import chdir

class TestSuccessfulFlow:
    def test_one_pr(self, repo_tar: Path, mocker: MockerFixture) -> None:
        mocker.patch('qram.git.push')
        with chdir(repo_tar):
            PR_NUMBER = 1
            cfg = Config()
            branches_global = BranchFormatter(cfg)
            branches_pr = branches_global.pr(PR_NUMBER)
            gh = GithubMock()
            pr: Pr = gh.get_pr(PR_NUMBER)

            # AT FIRST, repo is in pristine state, no markers exist
            all_branches_of_pr = [
                branches_pr.rebase_target, branches_pr.bad, branches_pr.source, branches_pr.merge,
            ]
            for branch in all_branches_of_pr:
                assert not git.branch_exists(branch)
            branch_origin = git.hash_of(pr.branch_head)

            # THEN, we prepare pr to be merged
            flow.prepare(1, gh, cfg)

            # AFTER THAT, push was called once - for queue branch
            assert git.push.call_count == 1

            # AND some new markers appear
            assert git.branch_exists(branches_pr.rebase_target)
            assert not git.branch_exists(branches_pr.bad)
            assert git.branch_exists(branches_pr.source)
            assert git.branch_exists(branches_pr.merge)

            branch_rebased = git.hash_of(pr.branch_head)
            source = git.hash_of(branches_pr.source)

            # AND source and rebase match original branch
            assert source == branch_origin
            assert branch_rebased == branch_origin, \
                "branch does not move for PR that is already on top"
            # AND merge-after-rebase matches new queue head
            assert git.hash_of(branches_pr.merge) == git.hash_of(branches_global.queue)
            # AND main DOES NOT match queue
            assert git.hash_of(branches_global.target) != git.hash_of(branches_global.queue)

            # THEN, we merge pr
            flow.merge(1, gh, cfg)

            # AFTER THAT, push was called twice more - for pr branch and main
            assert git.push.call_count == 3

            # AND markers disappear together with original branch
            for branch in [*all_branches_of_pr, pr.branch_head]:
                assert not git.branch_exists(branch)

            # AND main now matches queue
            assert git.hash_of(branches_global.target) == git.hash_of(branches_global.queue)
