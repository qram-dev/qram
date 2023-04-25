from qram.config import Config
from qram.github import Pr

from jinja2 import Environment

def format_merge_message(pr: Pr, config: Config) -> str:
    e = Environment()
    return e.from_string(
        source=config.merge_template.jinja,
        globals=dict(
            pr=pr,
            cfg=config
        )
    ).render().strip()

def format_author(pr: Pr) -> str:
    username = pr.author["username"]
    author_id = pr.author['id']
    email = f'{username}@users.noreply.github.com'
    if author_id:
        email = f'{author_id}+{email}'
    return f'{username} <{email}>'
