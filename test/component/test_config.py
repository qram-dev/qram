from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from qram.config import AppConfig, RepoConfig

from test import chdir


@pytest.fixture
def chtmp(tmp_path: Path) -> Generator[Path, None, None]:
    with chdir(tmp_path):
        yield tmp_path


# TODO: find proper type hint
@pytest.mark.parametrize('test_class', [AppConfig, RepoConfig])
def test_no_config_file(chtmp: Path, test_class: Any) -> None:
    with pytest.raises(FileNotFoundError):
        test_class.read_from_file()


@pytest.mark.parametrize('test_class', [AppConfig, RepoConfig])
def test_empty_file(chtmp: Path, test_class: Any) -> None:
    p = write_config('')
    with pytest.raises(ValidationError):
        test_class.read_from_file(p)

    p = write_config('---')
    with pytest.raises(ValidationError):
        test_class.read_from_file(p)


def test_unsupported_options() -> None:
    obj: Any = dict(
        omg=0,
        gitea=dict(),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('Extra inputs are not permitted')

    obj = dict(
        merge_template=dict(
            omg=0,
        ),
    )
    with pytest.raises(ValidationError) as e:
        RepoConfig.model_validate(obj)
    e.match('Extra inputs are not permitted')

    obj = dict(
        github=dict(
            omg=0,
        ),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('Extra inputs are not permitted')


def test_app_no_secret_file() -> None:
    obj: Any = dict(
        hmac_file='nosuchfile.txt',
        gitea=dict(),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('invalid file.*nosuchfile.txt')

    obj = dict(
        github=dict(
            app_id='1',
            installation_id='2',
            pem_file='nosuchfile.txt',
        ),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('invalid file.*nosuchfile.txt')


def test_app_empty_secret_file(chtmp: Path) -> None:
    Path('empty.txt').touch()

    obj: Any = dict(
        hmac_file='empty.txt',
        gitea=dict(),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('file is empty')

    obj = dict(
        github=dict(
            app_id='1',
            installation_id='2',
            pem_file='empty.txt',
        ),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('file is empty')


def test_app_invalid_provider() -> None:
    obj: Any = dict()
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('one of.*has to be specified')

    obj = dict(
        github=dict(app_id='', installation_id='', pem_file=__file__),
        gitea=dict(),
    )
    with pytest.raises(ValidationError) as e:
        AppConfig.model_validate(obj)
    e.match('only one of.*must be specified')


def test_app_valid_file(chtmp: Path) -> None:
    p = write_config(
        """
        github:
            app_id: '1'
            installation_id: '2'
            pem_file: qram.yml
    """
    )
    c = AppConfig.read_from_file(p)
    assert c.provider == 'github'
    assert c.github
    assert c.github.app_id == '1'
    assert c.github.installation_id == '2'
    assert c.github.pem.startswith('github:')


def test_repo_valid_file(chtmp: Path) -> None:
    p = write_config(
        """
        merge_template:
            jinja: x
            author:
                name: y
    """
    )
    c = RepoConfig.read_from_file(p)
    assert c.branching.branch_folder == 'mq'
    assert c.branching.target_branch == 'main'
    assert c.merge_template.jinja == 'x'
    assert c.merge_template.author.name == 'y'
    assert c.merge_template.author.email == 'qram@no.email'


###


def write_config(content: str) -> Path:
    p = Path('qram.yml')
    with p.open('w') as f:
        f.write(content)
    return p
