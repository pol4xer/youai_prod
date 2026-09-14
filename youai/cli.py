"""Command-line entry point for one story-to-video job."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from youai.application import NoStoryAvailable
from youai.config import Settings
from youai.domain import SortPeriod


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youai",
        description="Create a short-form video from the next Reddit story.",
    )
    parser.add_argument("--subreddit", default="pettyrevenge")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run an offline fictional story demo; write JSON storyboards, not videos.",
    )
    parser.add_argument(
        "--demo-dir",
        type=Path,
        default=Path("var/demo"),
        help=(
            "Directory for the isolated demo database and storyboards "
            "(default: var/demo)."
        ),
    )
    parser.add_argument(
        "--period",
        choices=[period.value for period in SortPeriod],
        default=SortPeriod.WEEK.value,
    )
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--video-provider")
    parser.add_argument("--email-provider")
    parser.add_argument("--email-address")
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    env = dict(os.environ)
    overrides = {
        "YOUAI_VIDEO_PROVIDER": args.video_provider,
        "YOUAI_EMAIL_PROVIDER": args.email_provider,
        "YOUAI_EMAIL_ADDRESS": args.email_address,
    }
    env.update({key: value for key, value in overrides.items() if value is not None})
    if args.headless is not None:
        env["YOUAI_HEADLESS"] = str(args.headless)
    return Settings.from_env(env)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.demo:
        from youai.demo import run_demo

        result = run_demo(args.demo_dir)
        logger = logging.getLogger(__name__)
        if result is None:
            logger.info("Demo story already processed in %s", args.demo_dir)
        else:
            logger.info(
                "Offline demo complete: JSON storyboards only; no video created."
            )
            for asset in result.media:
                logger.info("Wrote storyboard %s", asset.path)
        return 0

    from youai.bootstrap import create_pipeline

    try:
        with create_pipeline(_settings(args)) as pipeline:
            result = pipeline.run(
                category=args.subreddit,
                period=SortPeriod(args.period),
                max_pages=args.max_pages,
            )
    except NoStoryAvailable as error:
        logging.getLogger(__name__).info("%s", error)
        return 0

    for asset in result.media:
        logging.getLogger(__name__).info("Created %s", asset.path)
    return 0
