from pathlib import Path
from typing import Generator

import pytest
from schema import SchemaError

from qram.config import Config
from .. import chdir


@pytest.fixture(autouse=True)
def chtmp(tmp_path: Path) -> Generator[None, None, None]:
    with chdir(tmp_path):
        yield


def test_no_config() -> None:
    with pytest.raises(FileNotFoundError):
        Config.read_from_repo()


def test_empty() -> None:
    write_config('')
    with pytest.raises(TypeError):
        Config.read_from_repo()

    write_config('---')
    with pytest.raises(TypeError):
        Config.read_from_repo()


def test_unsupported_options() -> None:
    write_config('''
        app:
            provider: github
        omg: 0
    ''')
    with pytest.raises(SchemaError) as e:
        Config.read_from_repo()
    e.match(r".*Wrong key 'omg'")

    write_config('''
        app:
            provider: github
        merge-template:
            omg: 0
    ''')
    with pytest.raises(SchemaError) as e:
        Config.read_from_repo()
    e.match(r".*Wrong key 'omg'")

    write_config('''
        app:
            provider: github
            github:
                omg: 0
    ''')
    with pytest.raises(SchemaError) as e:
        Config.read_from_repo()
    e.match(r".*Missing keys.*app_id.*installation_id.*")


def test_values() -> None:
    write_config('''
        app:
            provider: github
            github:
                app_id: 1
                installation_id: 2
        branching:
            target-branch: a
            branch-folder: b/
    ''')
    c = Config.read_from_repo()
    assert c.app.provider == 'github'
    assert c.app.github
    assert c.app.github.app_id == 1
    assert c.app.github.installation_id == 2
    assert c.branching.target_branch == 'a'
    assert c.branching.branch_folder == 'b'
    assert c.merge_template.author.email == 'qram@no.email'

    write_config('''
        app:
            provider: github
            github:
                app_id: 1
                installation_id: 2
        merge-template:
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
    with open('qram.yml', 'w') as f:
        f.write(content)
