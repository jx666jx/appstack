#!/usr/bin/env python3
"""
Shared utilities for appstack scripts.

Provides:
- ANSI color constants and common glyphs
- Config loader with required app list
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
import shutil

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


def get_audio_output() -> str:
    """Get audio device information based on the operating system."""
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            result = subprocess.run(
                ["system_profiler", "SPAudioDataType"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        elif system == "Windows":
            # Use built-in CIM/WMI to list sound devices 
            ps_cmd = (
                "Get-CimInstance Win32_SoundDevice | "
                "Select-Object -ExpandProperty Name"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        elif system == "Linux":
            # Prefer PulseAudio/PipeWire sinks if available, else ALSA capture devices
            if shutil.which("pactl"):
                result = subprocess.run(
                    ["pactl", "list", "sinks", "short"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            elif shutil.which("arecord"):
                result = subprocess.run(
                    ["arecord", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            elif shutil.which("aplay"):
                result = subprocess.run(
                    ["aplay", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            else:
                raise FileNotFoundError("No pactl/arecord/aplay found")
        else:
            print(f"Unsupported operating system: {system}", file=sys.stderr)
            sys.exit(1)

        return result.stdout.lower()
    except FileNotFoundError as e:
        print(f"Error: Required command not found on {system}. {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: Audio device check timed out.", file=sys.stderr)
        sys.exit(1)


def check_audio_devices(device_list: list[str]) -> list[str]:
    """Check if required audio devices are connected. Returns list of missing devices."""
    output = get_audio_output()
    missing = [d for d in device_list if d.lower() not in output]
    return missing


__all__ = [
    "load_config",
    "get_audio_output",
    "check_audio_devices",
    "GREEN",
    "RED",
    "RESET",
    "BOLD",
    "CHECK",
    "CROSS",
]
