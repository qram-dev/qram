import logging
from argparse import ArgumentParser
from dataclasses import dataclass

from dotenv import load_dotenv

from qram.config import AppConfig
from qram.web.app import create_app, run_app


@dataclass
class Args:
    debug: bool


def parse_args() -> Args:
    p = ArgumentParser()
    _ = p.add_argument('--debug', action='store_true')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> int:
    # Initialize logging: time :: severity :: module :: msg
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True,
    )
    _ = load_dotenv()
    cfg = AppConfig.config_from_env()

    run_app(create_app(cfg), cfg, debug=args.debug)
    return 0


def _main() -> int:
    return main(parse_args())


if __name__ == '__main__':
    import sys

    sys.exit(_main())
