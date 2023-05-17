#!/usr/bin/env python3

import logging
from argparse import ArgumentParser
from dataclasses import dataclass

from dotenv import load_dotenv

from qram.config import Config
from qram.web.provider.github import github_api


@dataclass
class Args:
    github: bool


def parse_args() -> Args:
    p = ArgumentParser()
    p.add_argument('--github', action='store_true')
    return Args(**p.parse_args().__dict__)


def main(args: Args) -> None:
    if not any([args.github]):
        raise ValueError('no provider specified')
    logging.basicConfig(level=logging.DEBUG)
    load_dotenv(verbose=True)
    if args.github:
        cfg = Config.github_config_from_env()
        github_api(cfg).configure_webhook(cfg)


if __name__ == '__main__':
    main(parse_args())
