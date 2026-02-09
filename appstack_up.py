#!/usr/bin/env python3
"""
Automation script for streaming setup.

This script performs the following steps (configurable):
1. Suspend any running Fusion virtual machines
2. Disable MacOS sleep/screensaver/lock timers
3. Launch apps defined by config
"""

import subprocess
import time
import sys
from pathlib import Path
from util import GREEN, RED, RESET, CHECK, CROSS, load_config
from app_manager import start_apps


# REQUIRED
# A config file must be present or passed as the first argument to the script.
#
# Create a default config file at ~/.config/appstack/config.json:
# {
#   "apps": []
# }
#
# OPTIONAL
# Encrypted VM password mapping at: ~/.config/appstack/vm_passwords.json
#
# Example ~/.config/appstack/vm_passwords.json
# {
# 	"/Users/you/Virtual Machines.localized/YourVM/YourVM.vmx": "yourpassword"
# }


def disable_timeout():
    """Run timeout_manager.py to disable sleep/screensaver/lock."""
    print("Disabling sleep/screensaver/lock timers ...")
    try:
        script = Path(__file__).resolve().parent / "timeout_manager.py"
        subprocess.run([sys.executable, str(script), "disable"], check=True)
        print(f"{GREEN}{CHECK} Timers disabled.{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}{CROSS} Failed to run timeout_manager.py!{RESET}")
        sys.exit(1)


def suspend_vms():
    """Suspend all running virtual machines."""
    print("Suspending VMs...")
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "vm_manager.py"), "suspend"],
            check=True,
        )
        print(f"{GREEN}{CHECK} VMs suspended.{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}{CROSS} Failed to suspend VMs!{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    # Optional: pass a custom config file path as the first argument
    custom_cfg = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(custom_cfg)
    options = config.get("options", {})
    if options.get("suspend_vms") is True:
        suspend_vms()
        time.sleep(2)
    if options.get("disable_timeout") is True:
        disable_timeout()
    start_apps(config["apps"])
