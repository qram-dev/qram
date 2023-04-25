#!/usr/bin/env python3

import logging

from argparse import ArgumentParser
from os import chdir
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

import qram.git as git
from qram.github import Github

class Args(NamedTuple):
    target: str
    owner: str
    repo: str
    token_file: str
    root: str
    create_pr: Optional[str]
    prepare: Optional[int]
    merge: Tuple[str, str]
    generate_merges: int


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('target')
    p.add_argument('--owner', default='Artalus')
    p.add_argument('--repo', default='merge-test')
    p.add_argument('--token-file', default='token')
    p.add_argument('--root', default='root')
    p.add_argument('--create-pr')
    p.add_argument('--prepare', type=int, default=0)
    p.add_argument('--merge', nargs=2)
    p.add_argument('--generate-merges', type=int, default=0)
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG)
    chdir(args.target)
    gh = Github(Path(args.token_file).read_text().strip(), args.owner, args.repo)

    for i in range(1, 1+args.generate_merges):
        x = git.genhash()
        with git.switched_branch(x, args.root, True):
            git.commit(x)
            git.push(x)
        gh.create_pr(x, f'{i} - add {x}').json()

    if args.create_pr:
        gh.create_pr(args.create_pr, f'manually merge {args.create_pr}').json()

    if args.prepare:
        prepare(args.prepare, gh)

    if args.merge:
        pr_num, mergecommit = args.merge
        merge(int(pr_num), mergecommit, gh)

def merge(pr_num: int, mergecommit: str, gh: Github) -> None:
    pr = gh.get_pr(pr_num)
    # switch in case we are currently on moving branch
    with git.switched_branch(mergecommit, ''):
        git.check_call(['git', 'branch', 'main', '-f', mergecommit])
    git.push(pr.branch_head, True)
    git.push('main')

def prepare(pr_num: int, gh: Github) -> None:
    pr = gh.get_pr(pr_num)
    with git.switched_branch(pr.branch_head, ''):
        git.check_call(['git', 'rebase', 'merge-queue'])
    with git.switched_branch('merge-queue', ''):
        git.check_call(['git', 'merge', pr.branch_head, '--cleanup=whitespace', '--no-ff', '-m', f'#{pr_num}: {pr.title}'])
    git.push('merge-queue')


def _main() -> int:
    main(parse_args())
    return 0


if __name__ == '__main__':
    _main()
