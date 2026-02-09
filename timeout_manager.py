#!/usr/bin/env python3
"""
macOS Sleep and Screensaver Timeout Manager

This script provides a unified interface to manage macOS sleep, screensaver,
and lock timeout settings. Current settings are saved to a backup file
(~/.cache/timeout_manager.json) before modifications, allowing easy restoration.

Usage:
    ./timeout_manager.py              - Display menu
    ./timeout_manager.py disable      - Disable all sleep and lock timeouts
    ./timeout_manager.py restore      - Restore previous timeout settings
    ./timeout_manager.py -h           - Show help message

Note:
    Requires sudo access for pmset commands.
"""

import subprocess
import json
from pathlib import Path
import argparse
import os


SAVE_FILE = Path("~/.cache/timeout_manager.json").expanduser()


def ensure_cache_dir():
    """Ensure the cache directory exists."""
    try:
        SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create cache directory: {e}")


def run_command(cmd, get_output=False):
    """Run a shell command safely.

    Args:
        cmd (str): The shell command to execute.
        get_output (bool): If True, return command output as string.

    Returns:
        str or None: Output if get_output is True, else None.
    """
    try:
        if get_output:
            return subprocess.check_output(cmd, shell=True, text=True).strip()
        subprocess.run(cmd, shell=True, check=True)
        print(f"Executed: {cmd}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing '{cmd}': {e}")
        return None


def get_pmset_values():
    """Extract key pmset values for AC power.

    Returns:
        dict: Dictionary of pmset values (sleep, disksleep, displaysleep).
    """
    output = run_command("pmset -g custom", get_output=True)
    settings = {}
    if output:
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] in {"sleep", "disksleep", "displaysleep"}:
                settings[parts[0]] = parts[1]
    return settings


def get_current_settings():
    """Collect all relevant sleep/screensaver/lock settings.

    Returns:
        dict: Dictionary of current settings.
    """
    pmset = get_pmset_values()
    settings = {
        "pmset": pmset,
        "displaysleep": pmset.get("displaysleep"),
        "askForPassword": run_command(
            "defaults read com.apple.screensaver askForPassword", get_output=True
        ),
        "idleTime": run_command(
            "defaults -currentHost read com.apple.screensaver idleTime", get_output=True
        ),
        "askForPasswordDelay": run_command(
            "defaults read com.apple.screensaver askForPasswordDelay", get_output=True
        ),
    }
    return settings


def save_settings(settings):
    """Save settings dictionary to SAVE_FILE in JSON format.

    Args:
        settings (dict): Settings to save.
    """
    ensure_cache_dir()
    SAVE_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"💾 Saved current settings to {SAVE_FILE}")


def disable_sleep_and_lock():
    """Disable sleep, screensaver, and lock timers on macOS."""
    print("🔧 Disabling sleep, screensaver, and lock timers...")

    # Disable all system and display sleep timers
    run_command("sudo pmset -a sleep 0 displaysleep 0 disksleep 0")

    # Disable the screensaver lock and password prompt
    run_command("defaults -currentHost write com.apple.screensaver idleTime -int 0")
    run_command("defaults write com.apple.screensaver askForPassword -int 0")
    run_command("defaults write com.apple.screensaver askForPasswordDelay -int 0")

    # Disable screen lock and timeout in loginwindow domain
    run_command("defaults write com.apple.loginwindow DisableScreenLock -bool true")
    run_command("defaults write com.apple.loginwindow ScreenLockTimeout -int 0")

    # Disable lock screen (new macOS 14+ path)
    run_command(
        "defaults write -g com.apple.securitypref.lockScreenDisabled -bool true"
    )

    print("🔓 Sleep, screensaver, and lock timers fully disabled.")


def is_disabled(settings: dict) -> bool:
    """Return True if settings already match the disabled state.

    Compares a subset of keys we actively control. Missing values are treated
    as non-matching (i.e., return False).
    """
    pm = settings.get("pmset") or {}

    def eq0(val):
        return val is not None and str(val).strip() == "0"

    return (
        eq0(pm.get("sleep"))
        and eq0(pm.get("disksleep"))
        and eq0(pm.get("displaysleep"))
        and eq0(settings.get("askForPassword"))
        and eq0(settings.get("idleTime"))
        and eq0(settings.get("askForPasswordDelay"))
    )


def restore_settings():
    """Restore system sleep, screensaver, and lock settings from backup file."""
    if not SAVE_FILE.exists():
        print(f"❌ No saved settings found at {SAVE_FILE}")
        print("   Run 'disable' first to create a backup.")
        return

    with open(SAVE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print("🔄 Restoring previous settings...")

    # Restore pmset values if available
    pmset = data.get("pmset", {})
    sleep = pmset.get("sleep", 10)
    disksleep = pmset.get("disksleep", 10)
    displaysleep = pmset.get("displaysleep", 10)
    run_command(
        f"sudo pmset -a sleep {sleep} disksleep {disksleep} displaysleep {displaysleep}"
    )

    def _normalize_int(value, default: str) -> str:
        if value is None:
            return default
        try:
            return str(int(str(value).strip()))
        except (ValueError, TypeError):
            return default

    # Restore screensaver and lock settings
    ask = _normalize_int(data.get("askForPassword"), "1")
    idle = _normalize_int(data.get("idleTime"), "300")
    delay = _normalize_int(data.get("askForPasswordDelay"), "5")

    run_command(f"defaults write com.apple.screensaver askForPassword -int {ask}")
    run_command(
        f"defaults write com.apple.screensaver askForPasswordDelay -int {delay}"
    )
    run_command(
        f"defaults -currentHost write com.apple.screensaver idleTime -int {idle}"
    )

    # Restore loginwindow lock settings
    run_command("defaults delete com.apple.loginwindow DisableScreenLock || true")
    run_command("defaults delete com.apple.loginwindow ScreenLockTimeout || true")

    # Restore global lock screen setting (macOS 14+)
    run_command("defaults delete -g com.apple.securitypref.lockScreenDisabled || true")

    # Refresh preferences
    run_command("killall cfprefsd")
    # Optionally restart loginwindow (can force logout) if explicitly allowed
    if os.environ.get("APPSTACK_ALLOW_LOGINWINDOW_RESTART", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        run_command("killall -u $USER loginwindow || true")

    print("✅ All settings restored to previous values.")


def main():
    """Parse command-line arguments and manage timeout settings based on user input."""
    parser = argparse.ArgumentParser(
        description="Manage macOS sleep and timeout settings", add_help=False
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["disable", "restore"],
        help="Action to perform: 'disable' to disable timeouts,\
             'restore' to restore previous settings",
    )
    args = parser.parse_args()

    # Show menu if no action provided
    if args.action is None:
        print("⏱️  Timeout Manager")
        print("=" * 40)
        print("  disable  - Disable sleep & lock timeouts")
        print("  restore  - Restore previous settings")
        print("=" * 40)
        print("\nUsage: ./timeout_manager.py [disable|restore]")
        print("       ./timeout_manager.py -h for help\n")
        return

    if args.action == "disable":
        current = get_current_settings()
        if is_disabled(current):
            print("⚠️  Current settings already match disabled state; nothing to do.")
            return
        print("Saving current settings...")
        save_settings(current)

        print("Disabling sleep, screensaver, and lock...")
        disable_sleep_and_lock()

    elif args.action == "restore":
        restore_settings()


if __name__ == "__main__":
    main()
