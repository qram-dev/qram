from logging import getLogger
from typing import Iterable

import qram.git as git
from qram import (
    CommitAndBranches,
    collect_staging,
    format_author,
    format_merge_message,
    extract_pr_from_branch_list,
)
from qram.config import Config
from qram.formatter import BranchFormatter, PrFormatter
from qram.github import Github

logger = getLogger(__name__)

def _merge(pr_num: int, gh: Github, config: Config) -> None:
    logger.info(f'merge started for #{pr_num}')
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # sanity checks
    logger.info('checking branch preconditions')
    if not git.branch_exists(branches_pr.merge):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: its branch {pr.branch_head} has not been prepared yet')
    if not git.branch_exists(branches_pr.good):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: it is not marked as good')
    if git.branch_exists(branches_pr.bad):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: it is marked as bad')
    obstacles = list(collect_staging(f'{branches_pr.merge}~1', branches_global.target))
    if obstacles:
        raise RuntimeError(f'Cannot merge PR-{pr_num}: other PRs present in queue:\n{obstacles}')

    # switch in case we are currently on target branch
    logger.info('moving target to HEAD')
    with git.switched_branch(branches_pr.merge):
        git.check_call(['branch', branches_global.target, '-f', 'HEAD'])

    # First push pr branch, then push target, do it in 2 separate pushes. Otherwise github loses
    # its head and displays sillyness in PR commit list
    logger.info('pushing head')
    git.push(pr.branch_head, True)
    logger.info('pushing target')
    git.push(branches_global.target)
    git.check_call(['branch', '-D',
        branches_pr.merge, branches_pr.source, branches_pr.rebase, branches_pr.good, pr.branch_head
    ])
    logger.info(f'merge completed for #{pr_num}')


def prepare(pr_num: int, gh: Github, config: Config) -> None:
    logger.info(f'stage started for #{pr_num}')
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # mark original branch location as source, to use it for rebases later
    logger.info('remember source')
    if not git.branch_exists(branches_pr.source):
        git.check_call(['branch', branches_pr.source, pr.branch_head])

    # create merge queue branch if it does not exist yet
    logger.info('ensure queue exists')
    if not git.branch_exists(branches_global.queue):
        git.check_call(['branch', branches_global.queue, branches_global.target])

    # drop whatever state current branch is in right now, rebase it from original
    logger.info('move head to source')
    git.check_call(['branch', pr.branch_head, branches_pr.source, '-f'])

    logger.info('rebase onto queue')
    with git.switched_branch(pr.branch_head):
        # mark current queue head as target for rebase
        git.check_call(['branch', branches_pr.rebase, branches_global.queue, '-f'])
        git.check_call(['rebase', branches_pr.rebase])

    logger.info('create merge-commit')
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

    logger.info('push new queue')
    git.push(branches_global.queue)

    # once we enqueued branch, it is no longer bad nor good until we receive new status from ci
    logger.info('remove ci markers')
    if git.branch_exists(branches_pr.bad):
        git.check_call(['branch', '-D', branches_pr.bad])
    if git.branch_exists(branches_pr.good):
        git.check_call(['branch', '-D', branches_pr.good])
    logger.info(f'stage completed for #{pr_num}')


def mark_merge(pr_num: int, config: Config, ci_ok: bool) -> None:
    # FIXME: marking from CI/github will be done upon hash!! NOT upon PR number!
    logger.info(f'mark started for #{pr_num}')
    branches = BranchFormatter(config).pr(pr_num)
    if ci_ok:
        add = branches.good
        remove = branches.bad
    else:
        add = branches.bad
        remove = branches.good
    git.check_call(['branch', '-f', add, branches.merge])
    if git.branch_exists(remove):
        git.check_call(['branch', '-D', remove])
    logger.info(f'mark completed for #{pr_num}')


def shake_stage(gh: Github, config: Config) -> None:
    logger.info('shake started')
    branches_global = BranchFormatter(config)
    stage = list(reversed(list(collect_staging(branches_global.queue, branches_global.target))))
    logger.info('stage collected:' + ''.join(f'\n - {x}' for x in stage))
    for idx, (hash, branches) in enumerate(stage):
        pr = extract_pr_from_branch_list(branches, config)
        logger.info(f'check {hash} - #{pr}')
        branches_pr = branches_global.pr(pr)
        abort = False
        if branches_pr.good in branches and branches_pr.bad in branches:
            err = f'both {branches_pr.good} and {branches_pr.bad} are present on {hash}'
            logger.error(err)
            raise RuntimeError(err)

        if branches_pr.good in branches:
            logger.info('pr is good, merge it')
            _merge(pr, gh, config)
        elif branches_pr.bad in branches:
            logger.info('pr is bad, rebase remaining queue')
            # only way to get here should be if previous pr on stage was good. Ergo - it was merged,
            # target now points to its merge, and we should rebase onto it
            remaining = stage[idx+1:]
            _rebase_queue_onto(branches_global.target, remaining, gh, config)
            abort = True
        else:
            abort = True
        if abort:
            logger.info('shake completed, ignore rest of queue')
            return
    logger.info('shake completed, nothing left')


def _rebase_queue_onto(target: str, remaining: Iterable[CommitAndBranches], gh: Github, config: Config) -> None:
    logger.info('queue rebase started')
    branches_global = BranchFormatter(config)
    git.check_call(['branch', '-f', branches_global.queue, target])
    for hash, branches in remaining:
        pr = extract_pr_from_branch_list(branches, config)
        logger.info(f'rebasing {hash} - #{pr}')
        branches_pr = branches_global.pr(pr)
        if branches_pr.good in branches and branches_pr.bad in branches:
            err = f'both {branches_pr.good} and {branches_pr.bad} are present on {hash}'
            logger.error(err)
            raise RuntimeError(err)
        if branches_pr.bad in branches:
            logger.info('pr was marked bad, ignore it')
            continue
        else:
            logger.info('pr is not bad, re-enqueue it')
            prepare(pr, gh, config)
    logger.info('queue rebase completed')
