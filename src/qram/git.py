from collections.abc import Generator, Iterable
from contextlib import contextmanager
from logging import getLogger
from pathlib import Path
from random import choice
from subprocess import call as _call
from subprocess import check_call as _check_call
from subprocess import check_output as _check_output
from typing import Any, cast

from qram.types import Hash


logger = getLogger(__name__)


class Git:
    def __init__(self, repo_path: Path) -> None:
        self.repo = repo_path

    @contextmanager
    def switched_branch(
        self, branch: str, source: str = 'HEAD', *, anew: bool = False
    ) -> Generator[None, None, None]:
        if anew:
            call(self.repo, ['branch', '-D', branch])

        current = self.current_branch()
        check_call(self.repo, ['checkout', *(['-B', branch, source] if anew else [branch])])
        try:
            yield
        finally:
            check_call(self.repo, ['checkout', current])

    def current_branch(self) -> str:
        return check_output(self.repo, ['rev-parse', '--abbrev-ref', 'HEAD']).strip()

    def hash_of(self, ref: str) -> Hash:
        return Hash(check_output(self.repo, ['rev-parse', ref]).strip())

    def commit(self, x: str) -> None:
        with Path(x).open('w') as f:
            f.write(f'{x}\n')
        check_call(self.repo, ['add', x])
        check_call(self.repo, ['commit', '-m', x])

    def fetch(self) -> None:
        check_call(self.repo, ['fetch'])

    def push(self, x: str, *, force: bool = True) -> None:
        check_call(self.repo, ['push', '-u', 'origin', x, *(['--force'] if force else [])])

    def branch_exists(self, x: str) -> bool:
        return call(self.repo, ['show-ref', '--verify', '--quiet', f'refs/heads/{x}'])

    def log(self, head: str | Hash) -> Iterable[tuple[Hash, list[str]]]:
        """For each commit reachable from `head`, get (hash, [branch1, branch2, ...])"""
        sep = ' - '
        log = check_output(self.repo, ['log', f'--format=format:%h{sep}%D', f'{head}']).splitlines()
        splits = (tuple(line.split(sep)) for line in log)
        for commit, branches_line in splits:
            branches = extract_branches_from_line(branches_line)
            if branches:
                yield Hash(commit), branches

    def new_branch(self, branch: str, at: str | Hash = 'HEAD', *, force: bool = False) -> None:
        check_call(self.repo, ['branch', branch, at, *(['--force'] if force else [])])

    def delete_branch(self, *branches: str, force: bool = False) -> None:
        check_call(self.repo, ['branch', ('-D' if force else '-d'), *branches])

    def rebase(self, where: str | Hash) -> None:
        # FIXME: needs rollback if something fails
        check_call(self.repo, ['rebase', where])

    def clone(self, origin: str) -> None:
        check_call(self.repo, ['clone', origin, '.'])

    def merge(
        self, what: str | Hash, message: str, author: str, committer_name: str, committer_email: str
    ) -> None:
        # FIXME: needs rollback if something fails
        # plain `git merge` does not allow specifying author, so use --no-commit + `git commit`
        check_call(
            self.repo,
            [
                '-c',
                f'user.name={committer_name}',
                '-c',
                f'user.email={committer_email}',
                'merge',
                what,
                '--no-ff',
                '--no-commit',
            ],
        )
        check_call(
            self.repo,
            [
                '-c',
                f'user.name={committer_name}',
                '-c',
                f'user.email={committer_email}',
                'commit',
                '--author',
                author,
                '--cleanup=whitespace',
                '-m',
                message,
            ],
        )

    def branches_at_ref(self, ref: str | Hash) -> list[str]:
        output = check_output(self.repo, ['branch', '--points-at', ref])
        split = output.splitlines()
        # first 2 symbols are either `* ` for current branch or `  ` for the rest
        return [x[2:] for x in split]


def call(repo: Path, cmd: list[str], **kw: Any) -> bool:  # noqa: ANN401
    full_cmd = ['git']
    if repo.absolute() != Path().absolute():
        full_cmd += ['-C', str(repo)]
    full_cmd += cmd

    msg = f'CMD: {" ".join(full_cmd)}' + (f'| {kw}' if kw else '')
    logger.info(msg)
    c = _call(full_cmd, **kw)
    logger.info(f'--> {c}')
    return c == 0


def check_call(repo: Path, cmd: list[str], **kw: Any) -> None:  # noqa: ANN401
    full_cmd = ['git']
    if repo.absolute() != Path().absolute():
        full_cmd += ['-C', str(repo)]
    full_cmd += cmd

    msg = f'CMD: {" ".join(full_cmd)}' + (f'| {kw}' if kw else '')
    logger.info(msg)
    _check_call(full_cmd, **kw)


def check_output(repo: Path, cmd: list[str], **kw: Any) -> str:  # noqa: ANN401
    full_cmd = ['git']
    if repo.absolute() != Path().absolute():
        full_cmd += ['-C', str(repo)]
    full_cmd += cmd

    msg = f'CMD: {" ".join(full_cmd)}' + (f'| {kw}' if kw else '')
    logger.info(msg)
    return cast(bytes, _check_output(full_cmd, **kw)).decode()


def genhash() -> str:
    def ch() -> str:
        return chr(choice(list(range(ord('g'), ord('z') + 1))))  # noqa: S311

    return ''.join([ch() for _ in range(0, 11)])


def extract_branches_from_line(
    line: str,
    remote_list: list[str] = ['origin'],  # noqa: B006
) -> list[str]:
    remotes = tuple(f'{x.rstrip("/")}/' for x in remote_list)
    split = line.strip().split(', ')
    result: list[str] = []
    for x in split:
        if not x:
            continue
        if x == 'HEAD':
            continue
        if x.startswith(remotes):
            continue
        if x.startswith('tag: '):
            continue
        if '->' in x:
            _, x = x.split('->')  # noqa: PLW2901
        result.append(x.strip())
    return result
