#!/usr/bin/env python3

from argparse import ArgumentParser
from dataclasses import dataclass


@dataclass
class Args:
    pass


def parse_args() -> Args:
    p = ArgumentParser()
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> int:
    print('helo word')
    return 0


def _main() -> int:
    return main(parse_args())


if __name__ == '__main__':
    exit(_main())
