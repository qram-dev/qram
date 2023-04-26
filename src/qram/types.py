from os import PathLike
from typing import TypeAlias

StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]
