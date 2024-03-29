import re
from collections.abc import Callable, Iterable
from itertools import takewhile
from logging import getLogger
from typing import TypeVar

from jinja2 import Environment
from meiga import Error, Failure, Result, Success

from qram.config import RepoConfig
from qram.formatter import BranchFormatter, PrFormatter
from qram.git import Git
from qram.types import CommitAndBranches, Hash
from qram.web.provider import Pr, ProviderRepoApi

logger = getLogger(__name__)


def _merge(git: Git, pr_num: int, gh: ProviderRepoApi, config: RepoConfig) -> None:
    logger.info(f'merge started for #{pr_num}')
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # sanity checks
    logger.info('checking branch preconditions')
    if not git.branch_exists(branches_pr.merge):
        raise RuntimeError(
            f'Cannot merge PR-{pr_num}: its branch {pr.branch_head}' ' has not been prepared yet'
        )
    if not git.branch_exists(branches_pr.good):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: it is not marked as good')
    if git.branch_exists(branches_pr.bad):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: it is marked as bad')
    obstacles = list(collect_staging(git, f'{branches_pr.merge}~1', branches_global.target))
    if obstacles:
        raise RuntimeError(f'Cannot merge PR-{pr_num}: other PRs present in queue:\n{obstacles}')

    # switch in case we are currently on target branch
    logger.info('moving target to HEAD')
    with git.switched_branch(branches_pr.merge):
        git.new_branch(branches_global.target, force=True)

    # First push pr branch, then push target, do it in 2 separate pushes. Otherwise github loses
    # its head and displays sillyness in PR commit list
    logger.info('pushing head')
    git.push(pr.branch_head, force=True)
    logger.info('pushing target')
    git.push(branches_global.target)
    git.delete_branch(
        branches_pr.merge,
        branches_pr.source,
        branches_pr.rebase,
        branches_pr.good,
        pr.branch_head,
        force=True,
    )
    logger.info(f'merge completed for #{pr_num}')


def prepare(git: Git, pr_num: int, gh: ProviderRepoApi, config: RepoConfig) -> None:
    logger.info(f'stage started for #{pr_num}')
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # mark original branch location as source, to use it for rebases later
    logger.info('remember source')
    if not git.branch_exists(branches_pr.source):
        git.new_branch(branches_pr.source, pr.branch_head)

    # create merge queue branch if it does not exist yet
    logger.info('ensure queue exists')
    if not git.branch_exists(branches_global.queue):
        git.new_branch(branches_global.queue, branches_global.target)

    # drop whatever state current branch is in right now, rebase it from original
    logger.info('move head to source')
    git.new_branch(pr.branch_head, branches_pr.source, force=True)

    logger.info('rebase onto queue')
    with git.switched_branch(pr.branch_head):
        # mark current queue head as target for rebase
        git.new_branch(branches_pr.rebase, branches_global.queue, force=True)
        git.rebase(branches_pr.rebase)

    logger.info('create merge-commit')
    with git.switched_branch(branches_global.queue):
        message = format_merge_message(pr, config)
        author = format_author(pr)

        git.merge(
            pr.branch_head,
            message,
            author,
            config.merge_template.author.name,
            config.merge_template.author.email,
        )
        git.new_branch(branches_pr.merge, force=True)

    logger.info('push new queue')
    git.push(branches_global.queue)

    # once we enqueued branch, it is no longer bad nor good until we receive new status from ci
    logger.info('remove ci markers')
    to_delete: list[str] = []
    if git.branch_exists(branches_pr.bad):
        to_delete.append(branches_pr.bad)
    if git.branch_exists(branches_pr.good):
        to_delete.append(branches_pr.good)
    if to_delete:
        git.delete_branch(*to_delete, force=True)
    logger.info(f'stage completed for #{pr_num}')


def mark_merge(git: Git, pr_num: int, config: RepoConfig, *, ci_ok: bool) -> None:
    logger.info(f'mark started for #{pr_num}')
    branches_pr = BranchFormatter(config).pr(pr_num)
    if ci_ok:
        add = branches_pr.good
        remove = branches_pr.bad
    else:
        add = branches_pr.bad
        remove = branches_pr.good
    git.new_branch(add, branches_pr.merge, force=True)
    if git.branch_exists(remove):
        git.delete_branch(remove, force=True)
    logger.info(f'mark completed for #{pr_num}')


def shake_stage(git: Git, gh: ProviderRepoApi, config: RepoConfig) -> None:
    logger.info('shake started')
    branches_global = BranchFormatter(config)
    stage = list(
        reversed(
            list(
                collect_staging(git, branches_global.queue, branches_global.target),
            )
        )
    )
    stage_str = ''.join(f'\n - {x}' for x in stage)
    logger.info(f'stage collected: {stage_str}')
    for idx, (hash, branches) in enumerate(stage):
        match extract_pr_from_branch_list(branches, config):
            case Success(int()) as s:
                pr = s.value
            case Failure(NoMergesAtCommitError()) as e:
                # TODO: return
                raise RuntimeError(f'no merges found among {hash} - {branches}')
            case _ as e:
                raise AssertionError(f'unknown result: {e}')
        logger.info(f'check {hash} - #{pr}')
        branches_pr = branches_global.pr(pr)
        abort = False
        if branches_pr.good in branches and branches_pr.bad in branches:
            err = f'both {branches_pr.good} and {branches_pr.bad} are present on {hash}'
            logger.error(err)
            raise RuntimeError(err)

        if branches_pr.good in branches:
            logger.info('pr is good, merge it')
            _merge(git, pr, gh, config)
        elif branches_pr.bad in branches:
            logger.info('pr is bad, rebase remaining queue')
            # only way to get here should be if previous pr on stage was good. Ergo - it was merged,
            # target now points to its merge, and we should rebase onto it
            remaining = stage[idx + 1 :]
            _rebase_queue_onto(git, branches_global.target, remaining, gh, config)
            abort = True
        else:
            abort = True
        if abort:
            logger.info('shake completed, ignore rest of queue')
            return
    logger.info('shake completed, nothing left')


def _rebase_queue_onto(
    git: Git,
    target: str,
    remaining: Iterable[CommitAndBranches],
    gh: ProviderRepoApi,
    config: RepoConfig,
) -> None:
    logger.info('queue rebase started')
    branches_global = BranchFormatter(config)
    git.new_branch(branches_global.queue, target, force=True)
    for hash, branches in remaining:
        match extract_pr_from_branch_list(branches, config):
            case Success(int()) as s:
                pr = s.value
            case Failure(NoMergesAtCommitError()) as e:
                # TODO: return
                raise RuntimeError(f'no merges found among {hash} - {branches}')
            case _ as e:
                raise AssertionError(f'unknown result: {e}')
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
            prepare(git, pr, gh, config)
    logger.info('queue rebase completed')


class NoMergesAtCommitError(Error):
    pass


def format_merge_message(pr: Pr, config: RepoConfig) -> str:
    e = Environment(autoescape=True)
    return (
        e.from_string(
            source=config.merge_template.jinja,
            globals=dict(
                pr=pr,
                cfg=config,
            ),
        )
        .render()
        .strip()
    )


def format_author(pr: Pr) -> str:
    username = pr.author['username']
    author_id = pr.author['id']
    email = f'{username}@users.noreply.github.com'
    if author_id:
        email = f'{author_id}+{email}'
    return f'{username} <{email}>'


def collect_staging(
    git: Git, staging_branch: str, target_branch: str
) -> Iterable[CommitAndBranches]:
    log = git.log(staging_branch)
    queue = takewhile(lambda tpl: target_branch not in tpl[1], log)
    for commit, branches in queue:
        if any(b.endswith(PrFormatter.POSTFIX_MERGE) for b in branches):
            yield commit, branches


def _extract_pr_from_merge(branch: str, config: RepoConfig) -> int:
    prefix = config.branching.branch_folder
    postfix = PrFormatter.POSTFIX_MERGE
    regex = re.compile(f'{prefix}/pr(\\d+)/({postfix})')
    m = regex.search(branch)
    assert m is not None, f'string {branch} does not match regex'
    return int(m.group(1))


def extract_pr_from_branch_list(
    branches: list[str], config: RepoConfig
) -> Result[int, NoMergesAtCommitError]:
    for b in branches:
        if b.endswith(PrFormatter.POSTFIX_MERGE):
            return Success(_extract_pr_from_merge(b, config))
    logger.info(f'No merge postfix among branches: {branches}')
    return Failure(NoMergesAtCommitError())


def find_pr_matching_to_commit(
    commit: Hash, git: Git, config: RepoConfig
) -> Result[int, NoMergesAtCommitError]:
    branches = git.branches_at_ref(commit)
    return extract_pr_from_branch_list(branches, config)


T = TypeVar('T')


def takewhile_inclusive(predicate: Callable[[T], bool], iterable: Iterable[T]) -> Iterable[T]:
    for x in iterable:
        yield x
        if predicate(x):
            break
