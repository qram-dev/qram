import tarfile

from pathlib import Path

import pytest

@pytest.fixture(scope='function')
def repo_tar(tmp_path: Path) -> Path:
    d = tmp_path / 'repo'
    tar = Path(__file__).parent / 'assets/test-repo.tgz'
    with tarfile.open(tar) as f:
        f.extractall(path=d)
    return d
