from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, StrictStr, model_validator


logger = logging.getLogger(__name__)

class _CfgAuthor(BaseModel, extra='forbid'):
    name: StrictStr = 'qram'
    email: StrictStr = 'qram@no.email'

class _CfgMergeTemplate(BaseModel, extra='forbid'):
    author: _CfgAuthor = _CfgAuthor()
    jinja: StrictStr = '''#{{pr.number}}: {{pr.title}}

{{pr.body}}'''

class _CfgBranching(BaseModel, extra='forbid'):
    target_branch: StrictStr = 'main'
    branch_folder: StrictStr = 'mq'

    @model_validator(mode='after')
    def strip_trailing_slash(self) -> _CfgBranching:
        '''to avoid accidental //'s in paths'''
        self.branch_folder = self.branch_folder.strip('/')
        return self


def read_from_file(x: str) -> str:
    '''config.yaml has X_file, which is path - but in the object itself we
    want X field to be string contents of said file.'''
    p = Path(x)
    if not p or not p.is_file():
        raise ValueError(f'invalid file: {p.absolute()}')
    c = p.read_text().strip()
    if not c:
        raise ValueError(f'file is empty: {p.absolute()}')
    return c

class _CfgGithub(BaseModel, extra='forbid'):
    app_id: StrictStr
    installation_id: StrictStr
    pem: StrictStr = Field(alias='pem_file')
    webhook_url: StrictStr | None = None
    @model_validator(mode='after')
    def read_pem_from_file(self) -> _CfgGithub:
        self.pem = read_from_file(self.pem)
        return self

class _CfgGitea(BaseModel, extra='forbid'):
    pass

class _CfgApp(BaseModel, extra='forbid'):
    port: int = 8888
    hmac: StrictStr = Field('', alias='hmac_file')
    github: _CfgGithub | None = None
    gitea: _CfgGitea | None = None
    @model_validator(mode='after')
    def read_hmac_from_file(self) -> _CfgGithub:
        # validator is called always for the whole object, and empty hmac is a valid situation
        if self.hmac:
            self.hmac = read_from_file(self.hmac)
        return self

    @model_validator(mode='before')
    @classmethod
    def validate_providers(cls, field_values: Any) -> dict[str, Any]:
        assert isinstance(field_values, dict), 'can validator data be anything else?!'
        providers = ('gitea', 'github')
        present_providers = [field_values.get(p) is not None for p in providers]
        providers_string = ', '.join(f'"{p}"' for p in providers)
        if not any(present_providers):
            raise ValueError(f'one of {providers_string} fields has to be specified')
        if len([p for p in present_providers if p]) > 1:
            raise ValueError(f'only one of {providers_string} fields must be specified')
        return field_values


    @property
    def provider(self) -> str:
        if self.gitea:
            return 'gitea'
        if self.github:
            return 'github'
        return '?'


class Config(BaseModel, extra='forbid'):
    app: _CfgApp = _CfgApp.model_construct()
    branching: _CfgBranching = _CfgBranching.model_construct()
    merge_template: _CfgMergeTemplate = _CfgMergeTemplate.model_construct()


    @staticmethod
    def read_from_repo() -> Config:
        config_file = Path('qram.yml').absolute()
        if not config_file.exists():
            raise FileNotFoundError(f'config file {config_file} does not exist')

        with Path(config_file).open() as f:
            yy: dict[str, Any] = yaml.safe_load(f)
        return Config.model_validate(yy)


    @staticmethod
    def github_config_from_env() -> Config:
        c = Config.model_construct()
        c.app.hmac = os.environ['QRAM_APP_HMAC']
        pem = os.environ.get('QRAM_APP_GITHUB_PEM')
        if pem is None:
            pem = Path(os.environ['QRAM_APP_GITHUB_PEM_FILE']).read_text()
        c.app.github = _CfgGithub.model_construct(
            app_id = os.environ['QRAM_APP_GITHUB_APP_ID'],
            installation_id = os.environ['QRAM_APP_GITHUB_INSTALLATION_ID'],
            pem = pem.strip(),
            webhook_url = os.environ['QRAM_WEBHOOK_URL'],
        )
        return c
