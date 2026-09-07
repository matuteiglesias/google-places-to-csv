#!/usr/bin/env python3
"""Compatibility entry point for the canonical package CLI.

Prefer:
    python -m gmaps_scraper.cli ...

This file intentionally contains no independent Places API, billing, pagination,
or normalization logic so the repository has one runtime contract.
"""

from __future__ import annotations

import sys

from gmaps_scraper.cli import main


if __name__ == "__main__":
    print(
        "DEPRECATED: use `python -m gmaps_scraper.cli` instead of `python text_runner.py`.",
        file=sys.stderr,
    )
    raise SystemExit(main())
