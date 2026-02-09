#!/usr/bin/env python3
"""
Shared utilities for appstack scripts.

Provides:
- ANSI color constants and common glyphs
- Config loader with required app list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# COLORS / GLYPHS
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"
CHECK = "✅"
CROSS = "❌"


def _default_config_path() -> Path:
    return Path("~/.config/appstack/config.json").expanduser()


def load_config(cfg_file: str | Path | None = None) -> dict:
    """Load config from a JSON file and require a non-empty apps list."""
    if cfg_file is not None:
        cfg_path = Path(cfg_file).expanduser()
    else:
        cfg_path = _default_config_path()
    if not cfg_path.exists():
        print(f"Config file is required but not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Failed to read/parse config {cfg_path}: {e}", file=sys.stderr)
        sys.exit(1)

    apps = data.get("apps")
    if not (isinstance(apps, list) and apps):
        print(
            f"Config must include a non-empty 'apps' list: {cfg_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return data


__all__ = [
    "load_config",
    "GREEN",
    "RED",
    "RESET",
    "BOLD",
    "CHECK",
    "CROSS",
]
