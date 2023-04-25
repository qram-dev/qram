
import logging

from pathlib import Path
from typing import List, NamedTuple

import yaml

# # Config example:
# ---
# merge-template:
#   author: qram <qram>
#   jinja: |
#     #{{pr.number}}: {{pr.title}}
#
#     {{pr.body}}


logger = logging.getLogger(__name__)

class Config:
    merge_template: '_CfgMergeTemplate'

    @staticmethod
    def read_from_repo() -> 'Config':
        config_file = Path('qram.yml').absolute()
        with open(config_file) as f:
            yy = yaml.safe_load(f)
        cfg = Config()
        cfg.merge_template = _CfgMergeTemplate(**(yy['merge-template']))
        return cfg

class _CfgMergeTemplate(NamedTuple):
    author: str
    jinja: str
