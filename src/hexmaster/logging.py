# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

# src/hexmaster/logging.py
import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
