
import logging

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional as TOptional

from schema import Schema, Optional, And, Or, Literal, Use
import yaml


logger = logging.getLogger(__name__)

schema = Schema({
    'app': {
        Optional('port'): int,
        Optional('hmac_file'): And(Use(Path), Path.is_file),
        'provider': Or(
            Literal('github'),
        ),
        Optional('github'): {object: object},
    },
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

schema_github = Schema({
    'app_id': str,
    'installation_id': str,
    'pem_file':  And(Use(Path), Path.is_file),
})

@dataclass
class Config:
    app: '_CfgApp'
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

        app = yy.get('app', dict())
        hmac_path = app.get('hmac_file')
        hmac = Path(hmac_path).read_text().strip() if hmac_path else ''
        provider = app.get('provider')
        if provider == 'github':
            g = app.get('github')
            if type(g) is not dict:
                raise TypeError('app.github should be a dictionary')
            schema_github.validate(g)
            g['pem'] = Path(g.pop('pem_file')).read_text().strip()


        return Config(
            app=_CfgApp(
                port=app.get('port', _defaults.app.port),
                hmac=hmac or _defaults.app.hmac,
                provider=provider,
                github=_CfgGithub(**(app.get('github'))) if provider == 'github' else None,
            ),
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

@dataclass
class _CfgApp:
    port: int
    hmac: str
    provider: str
    github: TOptional['_CfgGithub']

@dataclass
class _CfgGithub:
    app_id: str
    installation_id: str
    pem: str



_defaults = Config(
    app=_CfgApp(
        port=8888,
        hmac='',
        provider='?',
        github=None,
    ),
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
