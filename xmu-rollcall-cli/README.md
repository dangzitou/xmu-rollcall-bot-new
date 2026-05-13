# xmu-rollcall-cli

A command-line tool for monitoring and auto-answering Tronclass rollcalls at Xiamen University.

> This project is intended for personal learning and automation convenience. Use it at your own risk and comply with your school's rules.

## Features

- Login with XMU unified authentication through `xmulogin`
- Continuous rollcall polling (1-second interval)
- Automatic handling for:
  - Number rollcalls (fetch number code and answer directly)
  - Radar rollcalls (location solving)
- Multi-account management in one local config
- Session cookie cache and refresh support
- Per-account notification settings for newly detected rollcalls
- Decoupled notification delivery through an external Hermes helper script

## Installation

Install from PyPI:

```bash
pip install xmu-rollcall-cli
```

After installation, these command aliases are available:

- `xmu`
- `xmu-rollcall-cli`
- `XMUrollcall-cli`

## Quick Start

1. Configure at least one account:

```bash
xmu config
```

2. (Optional) Switch active account:

```bash
xmu switch
```

3. Start monitoring:

```bash
xmu start
```

4. If session becomes invalid, refresh cookies:

```bash
xmu refresh
```

## Commands

- `xmu config` - Add/delete accounts and configure rollcall safety or notification delivery
- `xmu switch` - Switch the current account
- `xmu start` - Start rollcall monitoring loop
- `xmu refresh` - Remove cached cookies for current account
- `xmu --help` - Show help

## Configuration

The package stores local data in a `.xmu_rollcall` directory:

1. `XMU_ROLLCALL_CONFIG_DIR` (if set)
2. `~/.xmu_rollcall` (default)
3. `./.xmu_rollcall` (fallback when home is not writable)

Main files:

- `config.json`: account list and selected account
- `<account_id>.json`: cached cookies per account

Example (custom config directory):

```bash
export XMU_ROLLCALL_CONFIG_DIR="$HOME/Documents/.xmu_rollcall"
```

## Notification Delivery

Notifications for newly detected rollcalls are configured per account via `xmu config`.

### Design

The CLI only decides **when** to notify and **what** message to send. Actual delivery is delegated to:

- `scripts/send_rollcall_notification.py`
- Hermes `send_message_tool`

This keeps the rollcall logic isolated from direct chat delivery calls and makes deployments easier to reproduce.

### Target Modes

Each account stores notification settings like this:

- `enabled`: whether notifications are on for that account
- `notify_on_new_rollcall`: whether to notify immediately when a new rollcall is detected
- `target.type`:
  - `env`: resolve the final target from an environment variable at runtime
  - `fixed`: store the final target string directly in config
- `target.value`:
  - env mode: environment variable name, default `XMU_ROLLCALL_NOTIFY_TARGET`
  - fixed mode: a direct target such as `qqbot:YOUR_QQ_OPENID`

Recommended for deployment: use `env` mode so the config remains portable across machines and chat targets.

### Reproducible QQ Deployment Example

1. Configure notifications for the account:

```bash
xmu config
```

Then choose:

- `m` → Configure notification delivery
- enable notifications
- enable notify-on-new-rollcall
- target mode: `env`
- target value: `XMU_ROLLCALL_NOTIFY_TARGET`

2. Export the actual delivery target in the runtime environment:

```bash
export XMU_ROLLCALL_NOTIFY_TARGET="qqbot:YOUR_QQ_OPENID"
```

3. Start monitoring in the same environment:

```bash
xmu start
```

### Hermes Helper Contract

The helper accepts a single JSON argument:

```bash
python scripts/send_rollcall_notification.py '{"target":"qqbot:YOUR_QQ_OPENID","message":"hello"}'
```

Current behavior:

- For `qqbot:<openid>`, the helper maps the openid into `QQBOT_HOME_CHANNEL` and sends through Hermes' QQBot home-channel path.
- The rollcall package itself does not hardcode QQ-specific transport logic.
- If Hermes is unavailable or delivery fails, the monitoring loop keeps running and prints a notification error locally.

### Deployment Notes

- Ensure the Hermes repo path expected by `scripts/send_rollcall_notification.py` exists on the deployment machine. By default it uses `~/.hermes/hermes-agent`.
- Set `XMU_ROLLCALL_HERMES_REPO` if Hermes is checked out somewhere else.
- Ensure the Hermes environment is configured for the target platform before starting `xmu`.
- Prefer environment-based targets in production so secrets and chat IDs do not need to be committed into `config.json`.

## Limitations

- QR code rollcalls are currently **not supported**.
- This tool depends on Tronclass/XMU API behavior and may break if upstream endpoints change.
- Notification delivery depends on the external Hermes helper being available and configured.

## Supported Python Versions

- Python 3.7+

## Project Links

- Homepage: https://github.com/KrsMt-0113/XMU-Rollcall-Bot
- Issues: https://github.com/KrsMt-0113/XMU-Rollcall-Bot/issues

## License

MIT License
