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
