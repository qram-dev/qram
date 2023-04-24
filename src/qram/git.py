import logging

from contextlib import contextmanager
from random import choice
from subprocess import check_call as _check_call, check_output as _check_output

@contextmanager
def switched_branch(branch: str, source: str, anew: bool=False) -> None:
    if anew:
        try:
            check_call(['git', 'branch', '-D', branch])
        except:
            pass

    current = check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip()
    check_call(['git', 'checkout', *(['-B', branch, source] if anew else [branch])])
    try:
        yield
    finally:
        check_call(['git', 'checkout', current])

def genhash() -> str:
    def ch():
        return chr(choice(list(range(ord('g'), ord('z')+1))))
    return ''.join([ch() for _ in range(0,11)])

def commit(x: str) -> None:
    with open(x, 'w') as f:
        f.write(f'{x}\n')
    check_call(['git', 'add', x])
    check_call(['git', 'commit', '-m', x])

def push(x: str, force: bool=True) -> None:
    check_call(['git', 'push', '-u', 'origin', x, *(['--force'] if force else [])])

def check_call(cmd, *a, **kw) -> None:
    logging.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    _check_call(cmd, *a, **kw)

def check_output(cmd, *a, **kw) -> str:
    logging.info(f'CMD: {" ".join(cmd)}' + (f'| {kw}' if kw else ''))
    return _check_output(cmd, *a, **kw).decode()
