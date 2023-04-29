# mypy: ignore-errors
# mypy has not yet implemented support for TypeVarTuple
from typing import TypeVarTuple, Callable, Generator, Any, Tuple, Iterable

Ts = TypeVarTuple('Ts')
DataTable = Generator[Tuple[*Ts], None, None]

def datatable(*parsers: Callable[[str], Any]) -> Callable[[str], Any]:
    def parse_row(row: Iterable[str]) -> Tuple[Any]:
        return tuple(parser(cell) for parser, cell in zip(parsers, row))
    def parse_table(text: str) -> Generator[Any, None, None]:
        table = (_line_to_row(line) for line in _text_to_lines(text))
        # skip header row
        next(table)
        for row in table:
            yield parse_row(row)
    return parse_table

def _text_to_lines(text: str) -> Generator[str, None, None]:
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line

def _line_to_row(line: str) -> Iterable[str]:
    no_borders = line.strip('\t |')
    split = no_borders.split('|')
    return [x.strip() for x in split]

def str2bool(x: str) -> bool:
    if x.lower() in ('yes', 'true', 'y', 't'):
        return True
    if x.lower() in ('no', 'false', 'n', 'f'):
        return False
    raise ValueError(f'invalid string: {x}')
