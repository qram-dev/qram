
import logging

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

# # Config example:
# ---
# target-branch: main
# branch-folder: mq/
# merge-template:
#   author:
#     name: qram
#     email: qram@no.email
#   jinja: |
#     #{{pr.number}}: {{pr.title}}
#
#     {{pr.body}}


logger = logging.getLogger(__name__)

@dataclass
class Config:
    target_branch: str
    branch_folder: str
    merge_template: '_CfgMergeTemplate'

    def __init__(self, **yy: str|dict[str, str|dict[str, str]]) -> None:
        mt = yy.get('merge-template', _default_merge_template)
        if type(mt) is not dict:
            raise TypeError('`.merge-template` config element should be a dict')

        au = mt.get('author', dict())
        if type(au) is not dict:
            raise TypeError('`.merge-template.author` config element should be a dict')
        au_default = cast(dict[str, str], _default_merge_template['author'])

        name = au.get('name', au_default['name'])
        if type(name) is not str:
            raise TypeError('`.merge-template.author.name` config element should be a string')
        email = au.get('email', au_default['email'])
        if type(email) is not str:
            raise TypeError('`.merge-template.author.email` config element should be a string')

        jinja = mt.get('jinja', _default_merge_template['jinja'])
        if type(jinja) is not str:
            raise TypeError('`.merge-template.jinja` config element should be a string')

        self.merge_template = _CfgMergeTemplate(
            author=_CfgAuthor(name=name, email=email),
            jinja=jinja,
        )

        folder = yy.get('branch-folder', 'mq')
        if type(folder) is not str:
            raise TypeError('`.branch-folder` config element should be a string')
        self.branch_folder = folder.strip('/')

        target = yy.get('target-branch', 'main')
        if type(target) is not str:
            raise TypeError('`.target-branch` config element should be a string')
        self.target_branch = target

    @staticmethod
    def read_from_repo() -> 'Config':
        config_file = Path('qram.yml').absolute()
        if not config_file.exists():
            yy: dict[str, str] = dict()
        else:
            with open(config_file) as f:
                yy = yaml.safe_load(f)
                if type(yy) != dict:
                    raise RuntimeError('config file is not a dictionary')
        return Config(**yy)

@dataclass
class _CfgMergeTemplate:
    author: '_CfgAuthor'
    jinja: str

@dataclass
class _CfgAuthor:
    name: str
    email: str

_default_merge_template = dict(
    author=dict(
        name='qram',
        email='qram@no.email'
    ),
    jinja='''#{{pr.number}}: {{pr.title}}

{{pr.body}}'''
)
