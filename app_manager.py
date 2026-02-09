#!/usr/bin/env python3
"""
Generic app lifecycle helpers for appstack.

Supports config-driven start/stop definitions with healthchecks and
platform-specific blocks.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from util import GREEN, RED, RESET, CHECK, CROSS


def expand_path(path: str) -> str:
    """Expand ~ and environment variables in a file system path."""
    return os.path.expanduser(os.path.expandvars(path))


def process_exists_by_name(name: str) -> bool:
    """Return True if a process with the given name is running (System Events)."""
    try:
        res = subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to exists process "{name}"',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().lower() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def process_exists_by_cmd(fragment: str) -> bool:
    """Return True if a process exists whose command line contains the fragment.

    Uses `pgrep -f` which matches against full command line.
    """
    try:
        res = subprocess.run(["pgrep", "-f", fragment], capture_output=True, check=False)
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def wait_for_process_exit(
    *,
    name: str | None = None,
    fragment: str | None = None,
    timeout: float = 5.0,
    interval: float = 0.5,
) -> bool:
    """Poll until a process disappears or timeout."""
    end = time.time() + timeout
    while time.time() < end:
        exists_cmd = process_exists_by_cmd(fragment) if fragment else False
        exists_name = process_exists_by_name(name) if name else False
        if not (exists_cmd or exists_name):
            return True
        time.sleep(interval)
    return False

PLATFORM_KEYS = {"macos", "linux", "windows", "default"}


def _platform_name() -> str:
    """Return the normalized platform key for config selection."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _select_platform_block(block: Any) -> Any:
    """Return the platform-specific sub-block if provided."""
    if not isinstance(block, dict):
        return block
    candidates = {
        key: value
        for key, value in block.items()
        if key in PLATFORM_KEYS and isinstance(value, dict)
    }
    if not candidates:
        return block
    key = _platform_name()
    return candidates.get(key) or candidates.get("default") or {}


def _app_label(app: dict[str, Any]) -> str:
    """Return a display label for an app."""
    return str(app.get("name") or "App")


def _coerce_cmd(cmd: Any) -> list[str]:
    """Normalize a command into a list of args."""
    if isinstance(cmd, list):
        return [str(x) for x in cmd]
    if isinstance(cmd, str):
        return shlex.split(cmd)
    raise ValueError("cmd must be a list or string")


def _app_process_info(app: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract process name/fragment from an app definition."""
    proc = app.get("process") or {}
    return proc.get("name"), proc.get("cmd_fragment")


def app_is_running(app: dict[str, Any]) -> bool:
    """Return True if the app appears to be running."""
    proc_name, cmd_fragment = _app_process_info(app)
    running = False
    if cmd_fragment:
        running = running or process_exists_by_cmd(cmd_fragment)
    if proc_name:
        running = running or process_exists_by_name(proc_name)
    return running


def osascript_quit(target: str, *, by_bundle_id: bool = False) -> bool:
    """Attempt to quit a macOS app via AppleScript."""
    if by_bundle_id:
        script = f'tell application id "{target}" to quit'
    else:
        script = f'tell application "{target}" to quit'
    res = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, check=False
    )
    return res.returncode == 0


def kill_process_by_name(process_name: str, exclude: str | None = None) -> int:
    """Kill processes by name with an optional exclusion."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        killed = 0
        for line in lines:
            if process_name in line and "ps aux" not in line:
                if exclude and exclude in line:
                    continue
                fields = line.split()
                pid = fields[1]
                try:
                    os.kill(int(pid), 15)
                    killed += 1
                except (OSError, ProcessLookupError) as err:
                    print(f"{RED}{CROSS} Could not kill process {pid}: {err}{RESET}")
        return killed
    except subprocess.CalledProcessError as err:
        print(f"{RED}{CROSS} Error searching for {process_name}: {err}{RESET}")
        return 0


def wait_for_http(url: str, timeout: int = 300, interval: float = 2.0) -> bool:
    """Poll an HTTP URL until it returns 200 or timeout."""
    start = time.time()
    while True:
        try:
            response = urllib.request.urlopen(url, timeout=5)
            if response.status == 200:
                return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass
        if time.time() - start > timeout:
            return False
        time.sleep(interval)


def start_app(app: dict[str, Any]) -> None:
    """Start a single app based on its config."""
    if app.get("enabled", True) is False:
        return

    label = _app_label(app)
    if app_is_running(app):
        print(f"{GREEN}{CHECK} {label} already running. Skipping launch.{RESET}")
        return

    start = _select_platform_block(app.get("start") or {})
    method = start.get("method")
    print(f"Launching {label} ...")

    try:
        if method == "open_bundle":
            bundle_id = start["bundle_id"]
            args = ["open", "-b", bundle_id]
            path = start.get("path")
            if path:
                args.append(expand_path(path))
            extra_args = start.get("args")
            if extra_args:
                args.extend(["--args"] + [str(x) for x in extra_args])
            subprocess.run(args, check=True)
        elif method == "command":
            cmd = _coerce_cmd(start["cmd"])
            cwd = start.get("cwd")
            if cwd:
                cwd = expand_path(cwd)
            detached = bool(start.get("detached", True))
            if detached:
                subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            else:
                subprocess.run(cmd, cwd=cwd, check=True)
        elif method in {"none", None}:
            return
        else:
            print(f"{RED}{CROSS} Unknown start method for {label}: {method}{RESET}")
            return

        print(f"{GREEN}{CHECK} {label} launched.{RESET}")
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError) as err:
        print(f"{RED}{CROSS} Failed to launch {label}: {err}{RESET}")
        return

    health = app.get("healthcheck") or {}
    if health:
        url = health.get("url")
        if url:
            timeout = int(health.get("timeout", 300))
            interval = float(health.get("interval", 2.0))
            print(f"Waiting for {label} healthcheck: {url} ...")
            ok = wait_for_http(url, timeout=timeout, interval=interval)
            if ok:
                print(f"{GREEN}{CHECK} {label} is ready.{RESET}")
            else:
                print(f"{RED}{CROSS} Timed out waiting for {label}.{RESET}")


def stop_app(app: dict[str, Any]) -> None:
    """Stop a single app based on its config."""
    if app.get("enabled", True) is False:
        return

    label = _app_label(app)
    proc_name, cmd_fragment = _app_process_info(app)

    if not app_is_running(app):
        print(f"{GREEN}{CHECK} {label} not running.{RESET}")
        return

    print(f"Stopping {label} ...")
    stop = _select_platform_block(app.get("stop") or {})
    method = stop.get("method")
    kill_exclude = stop.get("kill_exclude")

    def wait_exit(timeout: float) -> bool:
        return wait_for_process_exit(name=proc_name, fragment=cmd_fragment, timeout=timeout)

    # 1) Graceful quit / command stop
    if method == "quit_bundle":
        bundle_id = stop.get("bundle_id")
        if bundle_id and osascript_quit(bundle_id, by_bundle_id=True) and wait_exit(5.0):
            print(f"{GREEN}{CHECK} {label} (AppleScript quit).{RESET}")
            return
    elif method == "quit_name":
        app_name = stop.get("app_name")
        if app_name and osascript_quit(app_name, by_bundle_id=False) and wait_exit(5.0):
            print(f"{GREEN}{CHECK} {label} (AppleScript quit).{RESET}")
            return
    elif method == "command":
        try:
            cmd = _coerce_cmd(stop["cmd"])
            cwd = stop.get("cwd")
            if cwd:
                cwd = expand_path(cwd)
            subprocess.run(cmd, cwd=cwd, check=True)
            if not (proc_name or cmd_fragment) or wait_exit(5.0):
                print(f"{GREEN}{CHECK} {label} (command).{RESET}")
                return
        except (OSError, subprocess.CalledProcessError, KeyError, ValueError) as err:
            print(f"{RED}{CROSS} Failed to stop {label}: {err}{RESET}")
            return

    # 2) pkill -f
    fragments = stop.get("pkill_fragments") or ([] if not cmd_fragment else [cmd_fragment])
    if isinstance(fragments, str):
        fragments = [fragments]
    for frag in fragments:
        if frag:
            subprocess.run(["pkill", "-f", frag], capture_output=True, check=False)
    if fragments and wait_exit(5.0):
        print(f"{GREEN}{CHECK} {label} (pkill).{RESET}")
        return

    # 3) name scan kill
    if proc_name:
        killed = kill_process_by_name(proc_name, exclude=kill_exclude)
        if killed and wait_exit(3.0):
            print(f"{GREEN}{CHECK} {label} (name scan).{RESET}")
            return

    print(f"{RED}{CROSS} {label} termination attempted but still detected running.{RESET}")


def start_apps(apps: list[dict[str, Any]]) -> None:
    """Start a list of apps in order."""
    for app in apps:
        start_app(app)


def stop_apps(apps: list[dict[str, Any]]) -> None:
    """Stop a list of apps in order."""
    for app in apps:
        stop_app(app)
