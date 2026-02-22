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

Missing any step or running them out of order meant problems at some point in the chain. The example configs under `examples/` capture those sequences so it is one command instead of a checklist. Swap configs to run different stacks.


## Quick Start

- Recommended: link the scripts into your path/bin
  ```bash
  chmod +x ./*.py
  ln -sf "$PWD/appstack_up.py" ~/.local/bin/appstack_up.py
  ln -sf "$PWD/appstack_down.py" ~/.local/bin/appstack_down.py
  ```

- Use the appstack examples in this repo:
  ```bash
  mkdir -p ~/.config/appstack
  cp ./examples/full.json ~/.config/appstack/config.json
  cp ./examples/work.json ~/.config/appstack/work.json
  chmod -R 700 ~/.config/appstack
  ```

- Start application stack with default config:
  ```bash
  appstack_up.py
  ```

- Stop application stack and restore settings:
  ```bash
  appstack_down.py
  ```

- Start different stack with alternate config:
  ```bash
  appstack_up.py ~/.config/appstack/work.json
  ```

- Stop different stack with alternate config:
  ```bash
  appstack_down.py ~/.config/appstack/work.json
  ```

## Configuration
A config file must be present at the default location (`~/.config/appstack/config.json`) or 
passed as the first argument to the script.
- Root keys:
  - `apps`: (required) ordered list of applications to start/stop
  - `options`: (optional) settings that control global behaviors

### Apps block
```json
  "apps": [
    {
      "name": "Loopback",
      "start": { "method": "open_bundle", "bundle_id": "com.rogueamoeba.Loopback" },
      "stop": { 
        "method": "quit_bundle", 
        "bundle_id": "com.rogueamoeba.Loopback",
        "pkill_fragments": ["Loopback"],
        "kill_exclude": "helper"
      },
      "process": { "name": "Loopback", "cmd_fragment": "Loopback" }
    }
  ]
}
```

Each app entry supports:
- `name` (string, required)
- `enabled` (bool, optional): skip if false
- `start` (object): how to start the app
  - `method`: `open_bundle` (macOS), `command`, or `none`
  - For `open_bundle`: `bundle_id`, optional `path`, optional `args`
  - For `command`: `cmd` (array), optional `cwd`, optional `detached`
  - Per-platform: nest under `start.macos` / `start.windows` / `start.linux`
- `stop` (object): how to stop the app
  - `method`: `quit_bundle` (macOS), `quit_name` (macOS), or `command`
  - `pkill_fragments` (array): extra command-line fragments to `pkill -f`
  - `kill_exclude` (string): substring to exclude when killing by name
  - Per-platform: nest under `stop.macos` / `stop.windows` / `stop.linux`
- `process` (object): how to detect if it is running
  - `name` (macOS System Events)
  - `cmd_fragment` (matched by `pgrep -f` on macOS/Linux)
  - Platform notes: On Windows, prefer explicit `stop.method: command` with `taskkill`; `pgrep` is not available.
- `healthcheck` (object, optional): URL readiness probe
  - `url` (string)
  - `timeout` (seconds)
  - `interval` (seconds)

#### Per‑Platform start/stop blocks
Per-platform app configurations are supported for `start`/`stop` blocks.

Selection order: current OS key (`macos`/`windows`/`linux`) → `default` → empty block (no-op for start; stop falls back to `pkill`/name-kill if `process` hints are present).
```json
{
  "apps": [
    {
      "name": "OBS",
      "start": {
        "macos": { "method": "command", "cmd": ["/Applications/OBS.app/Contents/MacOS/obs"] },
        "windows": { "method": "command", "cmd": ["C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"] }
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


### options block
```json
"options": {
  "suspend_vms": true,
  "disable_timeout": true,
  "restore_timeout": true,
  "start_vms": true,
  "stop_reverse": true,
  "audio_check": ["Universal Audio", "Expert Sleepers"]
}
```
If an option is empty or missing, it is skipped. All booleans default to `false`.
- `suspend_vms` (bool|string): suspend or stop running VMs before starting apps. Backwards compatible:
  - If `true` or the string value is `"suspend"`, `"paused"`, or `"pause"`, then suspend.
  - If the string value is `"stop"`, `"poweroff"`, or `"shutdown"`, then stop.
- `start_vms` (bool): list previously paused VMs to resume
- `disable_timeout` (bool): disable macOS sleep/screensaver/lock timers
- `restore_timeout` (bool): restore macOS sleep/screensaver/lock timers
- `stop_reverse` (bool): stop apps in reverse order of the list
- `audio_check` (string[]): audio interface names to verify are connected (cross‑platform); exits with error if any are missing


## VM passwords (Optional Config)
Create encrypted VM password mapping at: `~/.config/appstack/vm_passwords.json`. This is used to suspend any password encrypted VMs. Consider restricting the file permissions so only your user can read it: `chmod 600 ~/.config/appstack/vm_passwords.json`

**WARNING**: This is a security concern, as you are storing the unencrypted passwords for these VMs. 

```json
{
	"/Users/you/Virtual Machines.localized/YourVM/YourVM.vmx": "yourpassword"
}
```

## Script Reference

### appstack_up.py
- Orchestrate appstack startup sequence:
	- Optionally check if audio interfaces are available
  - Optionally suspend running VMs
	- Optionally disable macOS sleep/screensaver/lock
	- Launch apps defined in config

### appstack_down.py
- Orchestrate appstack shutdown sequence:
	- Stop apps defined in config
	- Optionally restore macOS sleep/screensaver/lock
	- Optionally list any paused VMs to resume

### examples/full.json
- Full example stack with options enabled.
- Includes entries for Ableton Live, TouchDesigner, Loopback, Stable Diffusion, and OBS.
- Uses `stop_reverse: true` so shutdown happens in reverse order.

### examples/work.json
- Lightweight example focused on a smaller app set to connect OBS to Zoom sessions.

### examples/minimal.json
- Minimal config showing only the required `apps` array and a no-op start.

### app_manager.py
- Config-driven start/stop helpers used by the up/down scripts.

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
- Cross-platform audio device detection (`get_audio_output`, `check_audio_devices`)

## Notes
- `timeout_manager.py` requires sudo for `pmset`.
- `vm_manager.py start` shows previously paused VMs for manual resume via VMware Fusion UI. Starting VMs with vmrun has proven to be problematic.
