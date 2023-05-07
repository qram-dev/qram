
import logging

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schema import Schema, Optional
import yaml


logger = logging.getLogger(__name__)

schema = Schema({
    Optional('branching'): {
        Optional('target-branch'): str,
        Optional('branch-folder'): str,
    },
    Optional('merge-template'): {
        Optional('author'): {
            Optional('name'): str,
            Optional('email'):  str,
        },
        Optional('jinja'): str,
    }
})

@dataclass
class Config:
    branching: '_CfgBranching'
    merge_template: '_CfgMergeTemplate'


    @staticmethod
    def read_from_repo() -> 'Config':
        config_file = Path('qram.yml').absolute()
        if not config_file.exists():
            raise FileNotFoundError(f'config file {config_file} does not exist')

        with open(config_file) as f:
            yy: dict[str, Any] = yaml.safe_load(f)
        if type(yy) is not dict:
            raise TypeError(f'{config_file} should contain a dictionary')
        schema.validate(yy)

        return Config(
            branching=_CfgBranching(
                target_branch=yy.get('branching', dict()) \
                    .get('target-branch', _defaults.branching.target_branch),
                branch_folder=yy.get('branching', dict()) \
                    .get('branch-folder', _defaults.branching.branch_folder).strip('/'),
            ),
            merge_template=_CfgMergeTemplate(
                author=_CfgAuthor(
                    name=yy.get('merge-template', dict()).get('author', dict()) \
                        .get('name', _defaults.merge_template.author.name),
                    email=yy.get('merge-template', dict()).get('author', dict()) \
                        .get('email', _defaults.merge_template.author.email),
                ),
                jinja=yy.get('merge-template', dict()) \
                    .get('jinja', _defaults.merge_template.jinja),
            )
        )

@dataclass
class _CfgMergeTemplate:
    author: '_CfgAuthor'
    jinja: str

@dataclass
class _CfgAuthor:
    name: str
    email: str

@dataclass
class _CfgBranching:
    target_branch: str
    branch_folder: str


_defaults = Config(
    branching=_CfgBranching(
        target_branch='main',
        branch_folder='mq',
    ),
    merge_template=_CfgMergeTemplate(
        author=_CfgAuthor(
            name='qram',
            email='qram@no.email',
        ),
        jinja='''#{{pr.number}}: {{pr.title}}

{{pr.body}}''',
    )
)
