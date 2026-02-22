#!/usr/bin/env python3
"""
Automation script for streaming setup.

This script performs the following steps (configurable):
1. Check audio interfaces are available
2. Suspend any running Fusion virtual machines
3. Disable MacOS sleep/screensaver/lock timers
4. Launch apps defined by config
"""

import subprocess
import time
import sys
from pathlib import Path
from util import GREEN, RED, RESET, CHECK, CROSS, load_config, check_audio_devices
from app_manager import start_apps


# REQUIRED
# A config file must be present or passed as the first argument to the script.
# Create a default config file at ~/.config/appstack/config.json:
# {
#   "apps": []
# }
#
# OPTIONAL
# Encrypted VM password mapping at: ~/.config/appstack/vm_passwords.json
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


def check_audio(audio_options: dict):
    """Check that all required audio interfaces are available."""
    audio_check = audio_options.get("audio_check", [])
    print("Checking audio interfaces...")
    missing = check_audio_devices(audio_check)
    if missing:
        print(f"{RED}{CROSS} Missing audio interface(s): {', '.join(missing)}{RESET}")
        sys.exit(1)
    print(f"{GREEN}{CHECK} All audio interfaces available.{RESET}")


def suspend_vms(vm_options: dict):
    """Suspend all running virtual machines."""
    val = vm_options.get("suspend_vms")
    # Determine action: boolean True -> suspend (legacy); string -> suspend/stop
    action = None
    if isinstance(val, bool):
        if val:
            action = "suspend"
    elif isinstance(val, str):
        v = val.strip().lower()
        if v in ("suspend", "paused", "pause"):
            action = "suspend"
        elif v in ("stop", "poweroff", "shutdown"):
            action = "stop"
    else:
        # No suspend_vms option provided
        return

    if action is None:
        print(f"{RED}{CROSS} Invalid suspend_vms option: {val}{RESET}")
        sys.exit(1)

    print(f"Applying VM action: {action} ...")
    try:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "vm_manager.py"),
                action,
            ],
            check=True,
        )
        print(f"{GREEN}{CHECK} VMs {action} completed.{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}{CROSS} Failed to {action} VMs!{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    # Optional: pass a custom config file path as the first argument
    custom_cfg = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(custom_cfg)
    options = config.get("options", {})
    if options.get("audio_check"):
        check_audio(options)
    if options.get("suspend_vms"):
        suspend_vms(options)
        time.sleep(2)
    if options.get("disable_timeout") is True:
        disable_timeout()
    start_apps(config["apps"])
