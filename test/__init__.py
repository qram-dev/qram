from contextlib import contextmanager
from os import chdir as _chdir
from os import getcwd
from typing import Generator

from qram.types import StrOrBytesPath


@contextmanager
def chdir(cd: StrOrBytesPath) -> Generator[None, None, None]:
    old = getcwd()
    _chdir(cd)
    try:
        yield
    finally:
        _chdir(old)
