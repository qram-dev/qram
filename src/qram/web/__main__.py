#!/usr/bin/env python3
import asyncio
import logging
from argparse import ArgumentParser
from dataclasses import dataclass

from qram.web.server import make_server
from qram.config import Config


logger = logging.getLogger(__name__)


@dataclass
class Args:
    debug: bool


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('--debug', action='store_true')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    config = Config.read_from_repo()
    server_coro = make_server(args.debug, config, args.debug)
    asyncio.run(server_coro)


def _main() -> None:
    main(parse_args())


if __name__ == '__main__':
    _main()
