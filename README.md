# appstack

appstack is a small, config‑driven launcher that brings a stack of apps up and down in a repeatable order.

This project was born from the drudgery and pitfalls of a manual, multi‑app startup process. Going live meant repeating the same checklist every time:
- Suspend any running [VMware Fusion](https://www.vmware.com/products/desktop-hypervisor/workstation-and-fusion) VMs
- Disable screensaver/lock timers
- Launch [Ableton Live](https://www.ableton.com/) with the correct template
- Launch [Loopback](https://rogueamoeba.com/loopback/)
- Launch [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) and wait for it to be available
- Launch [TouchDesigner](https://derivative.ca/) with the correct project
- Launch [OBS](https://obsproject.com/) with the right profile/collection/scene 

Shutting down was just as tedious and required performing the reverse of the startup sequence.

Missing any step or running them out of order meant problems at some point in the chain. `config.example.json` captures that full sequence so it is one command instead of a checklist. Swap configs to run different stacks (two examples are included).


## Quick Start

- Recommended: copy the scripts to your path/bin
  ```bash
  cp *.py ~/.local/bin
  chmod +x ~/.local/bin/*.py
  ```


- Alternative: keep the repo and symlink the launchers to your bin
  ```bash
  ln -sf "$PWD/appstack_up.py" ~/.local/bin/appstack_up.py
  ln -sf "$PWD/appstack_down.py" ~/.local/bin/appstack_down.py
  ```


- Use the appstack examples in this repo:
  ```bash
  mkdir -p ~/.config/appstack
  cp ./config.example.json ~/.config/appstack/config.json
  cp ./config.example2.json ~/.config/appstack/work.json
  chmod -R 700 ~/.config/appstack
  ```


- Start application stack with default config:
  ```bash
  appstack_up.py
  ```


- Start different stack with alternate config:
  ```bash
  appstack_up.py ~/.config/appstack/work.json
  ```


- Stop application stack and restore settings:
  ```bash
  appstack_down.py
  ```


- Stop different stack with alternate config:
  ```bash
  appstack_down.py ~/.config/appstack/work.json
  ```

## Required Config
A config file must be present at the default location or passed as the first argument to the script. The `apps` list is required and drives all start/stop behavior.

Create a default config at: `~/.config/appstack/config.json`
```json
{
  "options": {
    "suspend_vms": true,
    "disable_timeout": true,
    "restore_timeout": true,
    "start_vms": true,
    "stop_reverse": true
  },
  "apps": [
    {
      "name": "Loopback",
      "start": { "method": "open_bundle", "bundle_id": "com.rogueamoeba.Loopback" },
      "stop": { "method": "quit_bundle", "bundle_id": "com.rogueamoeba.Loopback" },
      "process": { "name": "Loopback", "cmd_fragment": "Loopback" }
    }
  ]
}
```

### Optional Config (VM passwords)
Create encrypted VM password mapping at: ~/.config/appstack/vm_passwords.json

```json
{
	"/Users/you/Virtual Machines.localized/YourVM/YourVM.vmx": "yourpassword"
}
```

### App List Format
If `apps` is missing or empty, the scripts will error.
Each app entry supports:
- `name` (string, required)
- `enabled` (bool, optional): skip if false
- `start` (object): how to start the app
- `stop` (object): how to stop the app
- `process` (object): how to detect if it is running
- `healthcheck` (object): optional URL check for readiness

### Options
These actions only run when explicitly set to `true`:
- `options.suspend_vms`: suspend running VMs before starting apps
- `options.start_vms`: list previously paused VMs to resume
- `options.disable_timeout`: disable macOS sleep/screensaver/lock timers
- `options.restore_timeout`: restore macOS sleep/screensaver/lock timers
- `options.stop_reverse`: stop apps in reverse order of the list

#### Start/Stop Methods
`start.method`:
- `open_bundle` (macOS): `{ "bundle_id": "...", "path": "...", "args": [...] }`
- `command` (cross‑platform): `{ "cmd": [...], "cwd": "...", "detached": true }`
- `none`: do nothing

`stop.method`:
- `quit_bundle` (macOS): `{ "bundle_id": "..." }`
- `quit_name` (macOS): `{ "app_name": "..." }`
- `command` (cross‑platform): `{ "cmd": [...], "cwd": "..." }`

Stop also supports:
- `pkill_fragments`: list of command‑line fragments to `pkill -f`
- `kill_exclude`: substring to skip when name‑killing

`process` supports:
- `name`: process name (macOS System Events)
- `cmd_fragment`: fragment matched by `pgrep -f`

`healthcheck` supports:
- `url`, `timeout` (seconds), `interval` (seconds)

#### Per‑Platform Blocks
Per-platform blocks are supported for `start`/`stop`:
```json
{
  "apps": [
    {
      "name": "OBS",
      "start": {
        "macos": { "method": "command", "cmd": ["/Applications/OBS.app/Contents/MacOS/obs"] },
        "windows": { "method": "command", "cmd": ["C:\\\\Program Files\\\\obs-studio\\\\bin\\\\64bit\\\\obs64.exe"] }
      },
      "stop": {
        "macos": { "method": "quit_bundle", "bundle_id": "com.obsproject.obs-studio" },
        "windows": { "method": "command", "cmd": ["taskkill", "/IM", "obs64.exe", "/T", "/F"] }
      },
      "process": { "cmd_fragment": "obs" }
    }
  ]
}
```

## Script Reference

### appstack_up.py
- Orchestrate appstack startup sequence:
	- Optionally suspend running VMs
	- Optionally disable macOS sleep/screensaver/lock
	- Launch apps defined in config

### appstack_down.py
- Orchestrate appstack shutdown sequence:
	- Stop apps defined in config
	- Optionally restore macOS sleep/screensaver/lock
	- Optionally list any paused VMs to resume

### config.example.json
- Full example stack with options enabled.
- Includes Ableton Live, TouchDesigner, Loopback, Stable Diffusion, and OBS entries.
- Uses `stop_reverse: true` so shutdown happens in reverse order.

### config.example2.json
- Lightweight example focused on a smaller app set to connect OBS to Zoom sessions.

### app_manager.py
- Config-driven start/stop helpers used by the start/stop scripts.

### timeout_manager.py
- Saves current power/screensaver/lock settings to `~/.cache/timeout_manager.json`.
- `disable`: Applies system-wide settings to prevent sleep, displaysleep, disksleep; disables screensaver password and lock.
- `restore`: Restores saved settings, refreshes prefs with `cfprefsd`. Optional, risky loginwindow restart is gated by env var `APPSTACK_ALLOW_LOGINWINDOW_RESTART=1`.

### vm_manager.py
- Manages VMware Fusion VMs using `vmrun`:
	- `stop`: Tries graceful stop, then hard stop.
	- `suspend`: Suspends running VMs.
	- `start`/`list`: Shows previously paused VMs for manual resume in Fusion UI.
- Saves the set of paused/stopped VMs to `~/.cache/vms-paused`.
- Optional password mapping: `~/.config/appstack/vm_passwords.json` with absolute `.vmx` paths mapping to passwords.

### util.py
- ANSI colors and glyphs for consistent output styling
- Shared config loader used by start/stop scripts

## Notes
- `timeout_manager.py` requires sudo for `pmset`.
- `vm_manager.py start` shows previously paused VMs for manual resume via VMware Fusion UI. Starting VMs with vmrun has proven to be problematic.
