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
        omg: 0
    ''')
    with pytest.raises(SchemaError) as e:
        Config.read_from_repo()
    e.match(r".*Wrong key 'omg'")

    write_config('''
        merge-template:
            omg: 0
    ''')
    with pytest.raises(SchemaError) as e:
        Config.read_from_repo()
    e.match(r".*Wrong key 'omg'")


def test_values() -> None:
    write_config('''
        branching:
            target-branch: a
            branch-folder: b/
    ''')
    c = Config.read_from_repo()
    assert c.branching.target_branch == 'a'
    assert c.branching.branch_folder == 'b'
    assert c.merge_template.author.email == 'qram@no.email'

    write_config('''
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
