"""Logging setup."""

import logging


def setup_logging(level: str) -> None:
    """Configure root logging with a single timestamped format at the given level."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
