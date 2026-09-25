"""Shared helpers: logging setup, hashing, and small formatting utilities."""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

from . import config


def get_logger(period: str) -> logging.Logger:
    """Return a logger that writes to both the console and a per-period log file.

    A dedicated log file per period gives an auditable record of every run,
    which is what makes reruns and failures debuggable after the fact.
    """
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"tlc.{period}")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers when the logger is requested more than once.
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(config.LOG_DIR / f"pipeline_{period}.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file (used to prove a cached raw input is intact)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human_bytes(n: int) -> str:
    """Format a byte count for human-readable logs."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"
