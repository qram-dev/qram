
import logging

from pathlib import Path
from typing import List, NamedTuple

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

class Config:
    target_branch: str
    branch_folder: str
    merge_template: '_CfgMergeTemplate'

    @staticmethod
    def read_from_repo() -> 'Config':
        config_file = Path('qram.yml').absolute()
        with open(config_file) as f:
            yy = yaml.safe_load(f)
            if type(yy) != dict:
                raise RuntimeError('config file is not a dictionary')
        cfg = Config()

        mt = yy.get('merge-template', _default_merge_template)
        au = mt.get('author', dict())
        a = _CfgAuthor(
            name=au.get('name', _default_merge_template['author']['name']),
            email=au.get('email', _default_merge_template['author']['email']),
        )
        cfg.merge_template = _CfgMergeTemplate(
            author=a,
            jinja=mt.get('jinja', _default_merge_template['jinja']),
        )
        cfg.branch_folder = yy.get('branch-folder', 'mq').strip('/')
        cfg.target_branch = yy.get('target-branch', 'main').strip('/')
        return cfg

class _CfgMergeTemplate(NamedTuple):
    author: '_CfgAuthor'
    jinja: str

class _CfgAuthor(NamedTuple):
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
