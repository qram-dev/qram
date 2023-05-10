from pathlib import Path

from qram.git import Git


class TestSwitchingBranches:
    def test_basic(self, repo_tar: Path) -> None:
        git = Git(repo_tar)
        assert git.current_branch() == 'main'
        assert git.branch_exists('do-1')
        with git.switched_branch('do-1'):
            assert git.current_branch() == 'do-1'
        assert git.current_branch() == 'main'

    def test_anew(self, repo_tar: Path) -> None:
        git = Git(repo_tar)
        assert git.current_branch() == 'main'
        assert not git.branch_exists('foo')
        with git.switched_branch('foo', anew=True):
            pass
        assert git.branch_exists('foo')


def test_branches_at_ref(repo_tar: Path) -> None:
    git = Git(repo_tar)
    for b in ('foo', 'bar', 'baz'):
        assert not git.branch_exists(b)
        assert b not in git.branches_at_ref('HEAD')
        git.new_branch(b)
        assert git.branch_exists(b)
    branches = git.branches_at_ref('HEAD')
    assert 'foo' in branches
    assert 'bar' in branches
    assert 'baz' in branches
