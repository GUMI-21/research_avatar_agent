"""Command-line entrypoint for the Avatar Agent Server."""

import argparse
import os

import uvicorn

from app.core.settings import SUPPORTED_ENVIRONMENTS, load_settings


def parse_args() -> argparse.Namespace:
    """Parse the required runtime environment."""
    parser = argparse.ArgumentParser(description="Start the Avatar Agent Server")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVIRONMENTS,
        help="Configuration environment to load",
    )
    return parser.parse_args()


def main() -> None:
    """Load configuration and start Uvicorn."""
    args = parse_args()
    os.environ["APP_ENV"] = args.env
    settings = load_settings(args.env)

    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    main()
