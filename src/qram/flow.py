
import qram.git as git
from qram import (
    find_merges_after,
    find_merges_before,
    format_author,
    format_merge_message,
)
from qram.config import Config
from qram.formatter import BranchFormatter, PrFormatter
from qram.github import Github


def merge(pr_num: int, gh: Github, config: Config) -> None:
    pr = gh.get_pr(pr_num)
    branches_global = BranchFormatter(config)
    branches_pr = branches_global.pr(pr_num)

    # sanity checks
    if not git.branch_exists(branches_pr.merge):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: its branch {pr.branch_head} has not been prepared yet')
    if git.branch_exists(branches_pr.bad):
        raise RuntimeError(f'Cannot merge PR-{pr_num}: it is marked as bad')
    merges = find_merges_before(branches_pr.merge, branches_global.target)
    # FIXME: need also check for /bad's !!
    if merges:
        raise RuntimeError(f'Cannot merge PR-{pr_num}: other PRs present in queue:\n{merges}')

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
    # once we enqueued branch, it is no longer bad until we receive new status from ci
    if git.branch_exists(branches_pr.bad):
        git.check_call(['branch', '-D', branches_pr.bad])


def mark_merge_bad(pr_num: int, gh: Github, config: Config) -> None:
    """
    Given merge X for which we got FAILURE from CI:
    - mark X as bad merge
    - find earliest merge below X that is not bad
    - drop existing queue above X
    - rebase everything above X to good merge, or to main if none found
    """
    branches_global = BranchFormatter(config)
    branches_bad_pr = branches_global.pr(pr_num)
    git.check_call(['branch', '-f', branches_bad_pr.bad, branches_bad_pr.merge])

    # if there are no merges before us, at least rebase onto main branch
    not_bad_merges = (
        candidate for candidate, branches in
        find_merges_before(branches_bad_pr.bad, config.target_branch, include_target_branch=True)
        if not any(b.endswith('/' + PrFormatter.BAD_POSTFIX) for b in branches)
    )
    destination = next(not_bad_merges)

    prs_above = [
        branches_bad_pr.extract_pr_from_branch_list(branches, config)
        for _, branches in find_merges_after(branches_bad_pr.bad, branches_global.queue)
    ]
    git.check_call(['branch', '-f', branches_global.queue, destination])
    git.check_call(['branch', '-D', branches_bad_pr.merge, branches_bad_pr.rebase_target])

    for pr_num in prs_above:
        pr_branch = gh.get_pr(pr_num).branch_head
        branches_above = branches_global.pr(pr_num)
        for b in pr_branch, branches_above.merge, branches_above.rebase_target:
            git.check_output(['branch', '-D', b])
        prepare(pr_num, gh, config)
