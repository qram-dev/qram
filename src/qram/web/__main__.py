import asyncio
import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from qram.config import AppConfig
from qram.web.server import make_server


logger = logging.getLogger(__name__)


@dataclass
class Args:
    debug: bool
    config_file: Path


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('--debug', action='store_true')
    p.add_argument('--config-file', type=Path, default='qram-app.yml')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    config = AppConfig.read_from_file(args.config_file)
    server_coro = make_server(
        config, debug=args.debug, provide_stop=args.debug, initialize_repos=True
    )
    asyncio.run(server_coro)


def _main() -> None:
    main(parse_args())


if __name__ == '__main__':
    _main()
