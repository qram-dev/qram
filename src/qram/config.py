
import logging

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schema import Schema, Optional
import yaml


logger = logging.getLogger(__name__)

schema = Schema({
    Optional('target-branch'): str,
    Optional('branch-folder'): str,
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
    target_branch: str
    branch_folder: str
    merge_template: '_CfgMergeTemplate'


    @staticmethod
    def read_from_repo() -> 'Config':
        config_file = Path('qram.yml').absolute()
        if not config_file.exists():
            yy: dict[str, Any] = dict()
        else:
            with open(config_file) as f:
                yy = yaml.safe_load(f)
            schema.validate(yy)

        return Config(
            target_branch=yy.get('target-branch', _defaults.target_branch),
            branch_folder=yy.get('branch-folder', _defaults.branch_folder).strip('/'),
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


_defaults = Config(
    target_branch='main',
    branch_folder='mq',
    merge_template=_CfgMergeTemplate(
        author=_CfgAuthor(
            name='qram',
            email='qram@no.email'
        ),
        jinja='''#{{pr.number}}: {{pr.title}}

{{pr.body}}''',
    )
)
