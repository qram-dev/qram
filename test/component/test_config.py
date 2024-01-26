from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from qram.config import Config

from test import chdir


@pytest.fixture
def chtmp(tmp_path: Path) -> Generator[Path, None, None]:
    with chdir(tmp_path):
        yield tmp_path


def test_no_config_file(chtmp: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Config.read_from_repo()


def test_empty_file(chtmp: Path) -> None:
    write_config('')
    with pytest.raises(ValidationError):
        Config.read_from_repo()

    write_config('---')
    with pytest.raises(ValidationError):
        Config.read_from_repo()


def test_unsupported_options() -> None:
    obj: Any = dict(
        omg=0,
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('extra fields not permitted')

    obj = dict(
        merge_template=dict(
            omg=0,
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('extra fields not permitted')

    obj = dict(
        app=dict(
            github=dict(
                omg=0,
            ),
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('extra fields not permitted')


def test_no_secret_file() -> None:
    obj: Any = dict(
        app=dict(
            hmac_file='nosuchfile.txt',
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('invalid file.*nosuchfile.txt')

    obj = dict(
        app=dict(
            github=dict(
                pem_file='nosuchfile.txt',
            ),
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('invalid file.*nosuchfile.txt')


def test_empty_secret_file(chtmp: Path) -> None:
    Path('empty.txt').touch()

    obj: Any = dict(
        app=dict(
            hmac_file='empty.txt',
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('file is empty')

    obj = dict(
        app=dict(
            github=dict(
                pem_file='empty.txt',
            ),
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('file is empty')


def test_invalid_provider() -> None:
    obj: Any = dict(
        app=dict(
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('one of.*has to be specified')

    obj = dict(
        app=dict(
            github=dict(app_id='', installation_id='', pem_file=__file__),
            gitea=dict(),
        ),
    )
    with pytest.raises(ValidationError) as e:
        Config.model_validate(obj)
    e.match('only one of.*must be specified')


def test_valid_file(chtmp: Path) -> None:
    write_config('''
        app:
            github:
                app_id: '1'
                installation_id: '2'
                pem_file: qram.yml
        branching:
            target_branch: a
            branch_folder: b/
    ''')
    c = Config.read_from_repo()
    assert c.app.provider == 'github'
    assert c.app.github
    assert c.app.github.app_id == '1'
    assert c.app.github.installation_id == '2'
    assert c.app.github.pem.startswith('app:')
    assert c.branching.target_branch == 'a'
    assert c.branching.branch_folder == 'b'
    assert c.merge_template.author.email == 'qram@no.email'

    write_config('''
        app:
            github:
                app_id: '1'
                installation_id: '2'
                pem_file: qram.yml
        merge_template:
            jinja: x
            author:
                name: y
    ''')
    c = Config.read_from_repo()
    assert c.branching.branch_folder == 'mq'
    assert c.branching.target_branch == 'main'
    assert c.merge_template.jinja == 'x'
    assert c.merge_template.author.name == 'y'
    assert c.merge_template.author.email == 'qram@no.email'

###

def write_config(content: str) -> None:
    with Path('qram.yml').open('w') as f:
        f.write(content)
