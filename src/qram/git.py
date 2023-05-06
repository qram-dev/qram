from contextlib import contextmanager
from logging import getLogger
from random import choice
from subprocess import (
    call as _call,
    check_call as _check_call,
    check_output as _check_output
)
from typing import Any, Generator, Iterable, List, NewType, Tuple, cast


logger = getLogger(__name__)

Hash = NewType('Hash', str)

@contextmanager
def switched_branch(branch: str, source: str='HEAD', anew: bool=False) -> Generator[None, None, None]:
    if anew:
        try:
            check_call(['branch', '-D', branch])
        except:
            pass

    current = current_branch()
    check_call(['checkout', *(['-B', branch, source] if anew else [branch])])
    try:
        yield
    finally:
        check_call(['checkout', current])

def current_branch() -> str:
    return check_output(['rev-parse', '--abbrev-ref', 'HEAD']).strip()

def hash_of(ref: str) -> Hash:
    return Hash(check_output(['rev-parse', ref]).strip())

def genhash() -> str:
    def ch() -> str:
        return chr(choice(list(range(ord('g'), ord('z')+1))))
    return ''.join([ch() for _ in range(0,11)])

def commit(x: str) -> None:
    with open(x, 'w') as f:
        f.write(f'{x}\n')
    check_call(['add', x])
    check_call(['commit', '-m', x])

def push(x: str, force: bool=True) -> None:
    check_call(['push', '-u', 'origin', x, *(['--force'] if force else [])])

def branch_exists(x: str) -> bool:
    return call(['show-ref', '--verify', '--quiet', f'refs/heads/{x}'])

def log(head: str|Hash) -> Iterable[Tuple[Hash, List[str]]]:
    """
    For each commit reachable from `head`, get (hash, [branch1, branch2, ...])
    """
    SEP = ' - '
    log = check_output([
        'log', f'--format=format:%h{SEP}%D', f'{head}'
    ]).splitlines()
    splits = (tuple(line.split(SEP)) for line in log)
    for hash, branches_line in splits:
        branches = extract_branches_from_line(branches_line)
        if branches:
            yield Hash(hash), branches


def call(cmd: List[str], *a: Any, **kw: Any) -> bool:
    cmd = ['git'] + cmd
    logger.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    c = _call(cmd, *a, **kw)
    logger.info(f'--> {c}')
    return c == 0

def check_call(cmd: List[str], *a: Any, **kw: Any) -> None:
    cmd = ['git'] + cmd
    logger.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    _check_call(cmd, *a, **kw)

def check_output(cmd: List[str], *a: Any, **kw: Any) -> str:
    cmd = ['git'] + cmd
    logger.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    return cast(bytes, _check_output(cmd, *a, **kw)).decode()


def extract_branches_from_line(line: str, remote_list: List[str]=['origin']) -> List[str]:
    remotes = tuple(f'{x.rstrip("/")}/' for x in remote_list)
    split = line.strip().split(', ')
    result: List[str] = []
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
            _, x = x.split('->')
        result.append(x.strip())
    return result
