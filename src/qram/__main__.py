#!/usr/bin/env python3

import logging

from argparse import ArgumentParser
from os import chdir
from pathlib import Path
from typing import NamedTuple, Optional, Tuple
from qram import format_author, format_merge_message
from qram.config import Config
from qram.formatter import BranchFormatter

import qram.git as git
from qram.github import Github

class Args(NamedTuple):
    target: str
    owner: str
    repo: str
    token_file: str
    root: str
    create_pr: Optional[str]
    prepare: int
    merge: int
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
    p.add_argument('--merge', type=int, default=0)
    p.add_argument('--generate-merges', type=int, default=0)
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG)
    chdir(args.target)
    config = Config.read_from_repo()
    gh = Github(Path(args.token_file).read_text().strip(), args.owner, args.repo)

    for i in range(1, 1+args.generate_merges):
        generate(args.root, i, gh)

    if args.create_pr:
        gh.create_pr(args.create_pr, f'manually merge {args.create_pr}').json()

    if args.prepare:
        prepare(args.prepare, gh, config)

    if args.merge:
        merge(args.merge, gh, config)


def generate(root: str, index: int, gh: Github) -> None:
    x = git.genhash()
    with git.switched_branch(x, root, True):
        git.commit(x)
        git.push(x)
    gh.create_pr(x, f'{index} - add {x}').json()


def merge(pr_num: int, gh: Github, config: Config) -> None:
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)
    # switch in case we are currently on target branch
    with git.switched_branch(branches_pr.merge):
        git.check_call(['branch', branches_global.target, '-f', 'HEAD'])
    # first push pr branch, then push target; do it in 2 separate pushes - otherwise github loses
    # its head and displays sillyness in PR commit list
    git.push(pr.branch_head, True)
    git.push(branches_global.target)
    for b in [branches_pr.merge, branches_pr.source, branches_pr.rebase_target]:
        git.check_call(['branch', '-D', b])


def prepare(pr_num: int, gh: Github, config: Config) -> None:
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # mark original branch location as source, to use it for rebases later
    if not git.branch_exists(branches_pr.source):
        git.check_call(['branch', branches_pr.source, pr.branch_head])

    # create merge queue branch if it does not exist yet
    if not git.branch_exists(branches_global.queue):
        git.check_call(['branch', branches_global.queue, branches_global.target])

    # drop whatever state current branch is in right now, rebase it from original
    git.check_call(['branch', pr.branch_head, branches_pr.source, '-f'])

    with git.switched_branch(pr.branch_head):
        # mark current queue head as target for rebase
        git.check_call(['branch', branches_pr.rebase_target, branches_global.queue, '-f'])
        git.check_call(['rebase', branches_pr.rebase_target])

    with git.switched_branch(branches_global.queue):
        message = format_merge_message(pr, config)
        author = format_author(pr)

        # `git merge` cannot format author, so use --no-commit + `git commit`
        git.check_call(['merge', pr.branch_head, '--no-ff', '--no-commit'])
        git.check_call([
            '-c', f'user.name={config.merge_template.author.name}',
            '-c', f'user.email={config.merge_template.author.email}',
            'commit',
            '--author', author,
            '--cleanup=whitespace', '-m', message,
        ])
        git.check_call(['branch', '-f', branches_pr.merge, 'HEAD'])

    git.push(branches_global.queue)


def _main() -> int:
    main(parse_args())
    return 0


if __name__ == '__main__':
    _main()
