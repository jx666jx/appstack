#!/usr/bin/env python3
"""
Automation script to stop streaming:

This script performs the following steps (configurable):
1. Stop apps defined by config
2. Restore MacOS sleep/screensaver/lock timers
3. List any paused VMs
"""

import subprocess
import sys
from pathlib import Path
from util import GREEN, RED, RESET, BOLD, CHECK, CROSS, load_config
from app_manager import stop_apps


def restore_timeout():
    """Run timeout_manager.py to restore sleep/screensaver/lock settings."""
    print("Restoring sleep/screensaver/lock settings ...")
    try:
        script = Path(__file__).resolve().parent / "timeout_manager.py"
        subprocess.run([sys.executable, str(script), "restore"], check=True)
        print(f"{GREEN}{CHECK} Timeout settings restored.{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}{CROSS} Failed to run timeout_manager.py!{RESET}")
        sys.exit(1)


def start_vms():
    """Start all previously paused virtual machines."""
    print("Starting paused VMs... (listing)")
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "vm_manager.py"), "start"],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"{RED}{CROSS} Failed to start VMs!{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    custom_cfg = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(custom_cfg)
    options = config.get("options", {})
    apps = config["apps"]
    if options.get("stop_reverse") is True:
        apps = list(reversed(apps))
    stop_apps(apps)
    if options.get("restore_timeout") is True:
        restore_timeout()
    if options.get("start_vms") is True:
        start_vms()
    print(f"\n{GREEN}{BOLD}✨ Stream stopped successfully!{RESET}")
