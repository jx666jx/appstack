#!/usr/bin/env python3
"""
VMware Fusion VM Management Tool

This script provides a unified interface to manage VMware Fusion virtual machines.
It supports starting, stopping, and suspending VMs.
Fusion is unreliable to start VMs via vmrun start; user must start manually from the UI

Usage:
    ./vm_manager.py              - Display menu
    ./vm_manager.py stop         - Stop all running VMs
    ./vm_manager.py suspend      - Suspend all running VMs
    ./vm_manager.py start        - Show previously paused VMs to resume
    ./vm_manager.py list         - Alias of 'start' (list paused VMs)
    ./vm_manager.py -h           - Show help message
"""

import subprocess
import os
import json
import argparse
import glob


# VMware virtual machines directory
VM_DIR = os.path.expanduser("~/Virtual Machines.localized/")
# Passwords config (override via env var APPSTACK_VM_PASSWORDS_FILE or APPSTACK_VM_PASSWORDS_JSON)
CONFIG_PASSWORDS_FILE = os.path.expanduser("~/.config/appstack/vm_passwords.json")
CACHE_DIR = os.path.expanduser("~/.cache")
CACHE_FILE = os.path.join(CACHE_DIR, "vms-paused")

def load_vm_passwords():
    """Load VM passwords mapping from env or config file.
    Precedence:
      1. APPSTACK_VM_PASSWORDS_JSON (JSON string mapping path->password)
      2. APPSTACK_VM_PASSWORDS_FILE (path to JSON mapping file)
      3. Default CONFIG_PASSWORDS_FILE (~/.config/appstack/vm_passwords.json) if exists
      4. Fallback to empty mapping
    """
    # Inline JSON via env
    inline = os.environ.get("APPSTACK_VM_PASSWORDS_JSON")
    if inline:
        try:
            data = json.loads(inline)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            print("Warning: Invalid JSON in APPSTACK_VM_PASSWORDS_JSON; ignoring.")

    # File path via env
    cfg_path = os.environ.get("APPSTACK_VM_PASSWORDS_FILE")
    if cfg_path:
        cfg_path = os.path.expanduser(cfg_path)
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load passwords from {cfg_path}: {e}")

    # Default config file
    try:
        if os.path.exists(CONFIG_PASSWORDS_FILE):
            with open(CONFIG_PASSWORDS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to load passwords from {CONFIG_PASSWORDS_FILE}: {e}")

    return {}


def ensure_cache_dir():
    """Ensure the cache directory exists."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create cache directory: {e}")


def save_paused_vms(vms):
    """Save list of paused VMs to cache file."""
    try:
        ensure_cache_dir()
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for vm in vms:
                f.write(f"{vm}\n")
    except IOError as e:
        print(f"Warning: Could not save paused VMs to cache: {e}")


def load_paused_vms():
    """Load list of previously paused VMs from cache file."""
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except IOError as e:
        print(f"Warning: Could not read paused VMs from cache: {e}")
        return []


def list_vms():
    """Return a list of running VM paths."""
    try:
        result = subprocess.run(
            ["vmrun", "-T", "fusion", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().splitlines()
        # Skip the first line: "Total running VMs: N"
        return [line.strip() for line in lines[1:] if line.strip()]
    except subprocess.CalledProcessError as e:
        print("Error listing VMs:", e.stderr.strip())
        return []


def list_suspended_vms():
    """Return a list of suspended VM paths by finding .vmx files."""
    try:
        vmx_files = glob.glob(f"{VM_DIR}/**/*.vmx", recursive=True)
        return vmx_files
    except (OSError, ValueError) as e:
        print("Error listing suspended VMs:", str(e))
        return []


def manage_vm(vmx_path, action, password=None):
    """Manage a single VM by its .vmx path with the specified action (stop, suspend, or start).

    Args:
        vmx_path (str): Path to the .vmx file
        action (str): Action to perform ('stop', 'suspend', or 'start')
        password (str): Optional password for encrypted VMs
    """
    if action == "stop":
        action_display = "Stopping"
        action_past = "Stopped"
    elif action == "suspend":
        action_display = "Suspending"
        action_past = "Suspended"
    else:  # start
        action_display = "Starting"
        action_past = "Started"

    print(f"{action_display} VM: {vmx_path}")

    base_cmd = ["vmrun", "-T", "fusion"]
    if password:
        base_cmd.extend(["-vp", password])

    if action == "start":
        # Encrypted VMs are unreliable to start via vmrun on Fusion; ask user to start manually
        if password:
            print(
                "🔒 Encrypted VM detected. Starting via vmrun is unreliable on Fusion. "
                "Please start this VM from VMware Fusion UI:\n  " + vmx_path
            )
            return

        cmd = base_cmd + ["start", vmx_path, "nogui"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"✅ {action_past}: {vmx_path}")
        else:
            detail = (res.stderr or res.stdout or "").strip() or "The operation failed"
            # Common Fusion errors when vmrun cannot start VMs
            if (
                "operation is not supported" in detail.lower()
                or "locationgetroot" in detail.lower()
            ):
                print("ℹ️ Please start this VM from the VMware Fusion UI.")
            print(f"❌ Failed to {action} {vmx_path}: {detail}")
        return

    if action == "stop":
        # Try graceful stop with 60s timeout, then hard stop
        graceful_cmd = base_cmd + ["stop", vmx_path]
        try:
            res = subprocess.run(
                graceful_cmd, capture_output=True, text=True, timeout=60, check=False
            )
            if res.returncode == 0:
                print(f"✅ {action_past}: {vmx_path}")
                return
            else:
                detail = (res.stderr or res.stdout or "").strip()
                if detail:
                    print(f"⚠️  Graceful stop reported error: {detail}")
        except subprocess.TimeoutExpired:
            print("⏳ Graceful stop exceeded 60s; forcing hard stop...")

        # Hard stop fallback
        hard_cmd = base_cmd + ["stop", vmx_path, "hard"]
        res2 = subprocess.run(
            hard_cmd, capture_output=True, text=True, timeout=60, check=False
        )
        if res2.returncode == 0:
            print(f"✅ {action_past} (hard): {vmx_path}")
        else:
            detail = (
                res2.stderr or res2.stdout or ""
            ).strip() or "The operation failed"
            print(f"❌ Failed to hard stop {vmx_path}: {detail}")
        return

    if action == "suspend":
        cmd = base_cmd + ["suspend", vmx_path]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"✅ {action_past}: {vmx_path}")
        else:
            detail = (res.stderr or res.stdout or "").strip() or "The operation failed"
            print(f"❌ Failed to {action} {vmx_path}: {detail}")


def main():
    """
    Parse command-line arguments and manage VMs based on user input.

    Supports actions: 'stop', 'suspend', or 'start'.
    Lists all running VMs and applies the specified action to each one.
    If no action is provided, displays a menu for user selection.
    """
    vm_passwords = load_vm_passwords()
    parser = argparse.ArgumentParser(description="Manage running VMs", add_help=False)
    parser.add_argument(
        "action",
        nargs="?",
        choices=["stop", "suspend", "start", "list"],
        help="Action: 'stop' or 'suspend' running VMs; 'start'/'list' shows paused VMs for manual resume",
    )
    args = parser.parse_args()

    # Show menu if no action provided
    if args.action is None:
        print("\n🎯 VM Management Menu")
        print("=" * 40)
        print("1. stop     - Stop all running VMs")
        print("2. suspend  - Suspend all running VMs")
        print("3. start    - Show paused VMs for manual start")
        print("=" * 40)
        print("\nUsage: ./vm_manager.py [stop|suspend|start|list]")
        print("       ./vm_manager.py -h for help\n")
        return

    # Map user input to vmrun command
    vms = []
    vm_type = ""
    vmrun_action = ""

    if args.action == "stop":
        save_paused_vms([])  # Clear cache before stopping
        vms = list_vms()
        vm_type = "running"
        vmrun_action = "stop"
    elif args.action == "suspend":
        save_paused_vms([])  # Clear cache before suspending
        vms = list_vms()
        vm_type = "running"
        vmrun_action = "suspend"
    elif args.action in ["start", "list"]:
        vms = load_paused_vms()
        vm_type = "paused"
        vmrun_action = None
        # No vmrun for list; handled below

    if not vms:
        print(f"No {vm_type} VMs found.")
        return

    # For 'list', just inform the user which VMs were paused and exit
    if args.action in ["start", "list"]:
        print(
            f"Found {len(vms)} paused VM(s). The following VMs were previously in use:"
        )
        for vmx in vms:
            print(f"  • {vmx}")
        print("\nPlease start these VMs from the VMware Fusion UI.")
        return

    print(f"Found {len(vms)} {vm_type} VM(s).")
    for vmx in vms:
        # Look up password for this VM if it exists
        normalized_vmx = os.path.realpath(os.path.expanduser(vmx))
        password = None
        for key, pw in vm_passwords.items():
            if normalized_vmx == os.path.realpath(os.path.expanduser(key)):
                password = pw
                break
        manage_vm(vmx, vmrun_action, password=password)

    # Save paused VMs to cache after stopping or suspending
    if args.action in ["suspend", "stop"]:
        save_paused_vms(vms)


if __name__ == "__main__":
    main()
