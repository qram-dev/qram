from pathlib import Path

import qram.git as git

from .. import chdir

class TestSwitchingBranches:
    def test_basic(self, repo_tar: Path) -> None:
        with chdir(repo_tar):
            assert git.current_branch() == 'main'
            assert git.branch_exists('do-1')
            with git.switched_branch('do-1'):
                assert git.current_branch() == 'do-1'
            assert git.current_branch() == 'main'

    def test_anew(self, repo_tar: Path) -> None:
        with chdir(repo_tar):
            assert git.current_branch() == 'main'
            assert not git.branch_exists('foo')
            with git.switched_branch('foo', anew=True):
                pass
            assert git.branch_exists('foo')
