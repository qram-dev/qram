#!/usr/bin/env python3

import logging

from argparse import ArgumentParser
from os import chdir
from pathlib import Path
from typing import NamedTuple, Optional

from qram import git
from qram.flow import (
    mark_merge_bad,
    merge,
    prepare,
)
from qram.config import Config
from qram.github import Github


class Args(NamedTuple):
    target: str
    command: str
    pr: int
    owner: str
    repo: str
    token_file: str
    token: Optional[str]
    root: str


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('target')
    p.add_argument('command', choices=('generate', 'prepare', 'merge', 'bad'))
    p.add_argument('pr', type=int)
    p.add_argument('--owner', default='Artalus')
    p.add_argument('--repo', default='merge-test')
    p.add_argument('--token')
    p.add_argument('--token-file', default='token')
    p.add_argument('--root', default='root')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG)
    chdir(args.target)
    config = Config.read_from_repo()
    token = args.token if args.token else Path(args.token_file).read_text().strip()
    gh = Github(token, args.owner, args.repo)

    if args.command == 'generate':
        for i in range(1, 1 + args.pr):
            generate(args.root, i, gh)
    elif args.command == 'prepare':
        prepare(args.pr, gh, config)
    elif args.command == 'merge':
        merge(args.pr, gh, config)
    elif args.command == 'bad':
        mark_merge_bad(args.pr, gh, config)


def generate(root: str, index: int, gh: Github) -> None:
    x = git.genhash()
    branch = f'do-{x}'
    with git.switched_branch(branch, root, True):
        git.commit(x)
        git.push(branch)
    gh.create_pr(branch, f'{index} - add {x}').json()


def _main() -> int:
    main(parse_args())
    return 0


if __name__ == '__main__':
    _main()
