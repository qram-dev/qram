import logging

from contextlib import contextmanager
from random import choice
from subprocess import (
    call as _call,
    check_call as _check_call,
    check_output as _check_output
)
from typing import Any, Generator, List

@contextmanager
def switched_branch(branch: str, source: str='HEAD', anew: bool=False) -> Generator[None, None, None]:
    if anew:
        try:
            check_call(['branch', '-D', branch])
        except:
            pass

    current = check_output(['rev-parse', '--abbrev-ref', 'HEAD']).strip()
    check_call(['checkout', *(['-B', branch, source] if anew else [branch])])
    try:
        yield
    finally:
        check_call(['checkout', current])

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

def call(cmd: List[str], *a: Any, **kw: Any) -> bool:
    cmd = ['git'] + cmd
    logging.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    c = _call(cmd, *a, **kw)
    logging.info(f'--> {c}')
    return c == 0

def check_call(cmd: List[str], *a: Any, **kw: Any) -> None:
    cmd = ['git'] + cmd
    logging.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    _check_call(cmd, *a, **kw)

def check_output(cmd: List[str], *a: Any, **kw: Any) -> str:
    cmd = ['git'] + cmd
    logging.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    return _check_output(cmd, *a, **kw).decode()
