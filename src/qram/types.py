from os import PathLike
from typing import NewType, TypeAlias

Hash = NewType('Hash', str)

StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]
CommitAndBranches = tuple[Hash, list[str]]
