> Forked from [KrsMt-0113/XMU-Rollcall-Bot](https://github.com/KrsMt-0113/XMU-Rollcall-Bot)

<div align="center">

# XMU Rollcall Bot

<p>
  <img src="https://img.shields.io/badge/Python-3.7%2B-blue" />
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-0f766e" />
  <img src="https://img.shields.io/badge/CLI-Tool-7c3aed" />
  <img src="https://img.shields.io/badge/XMU-TronClass-ef4444" />
  <img src="https://img.shields.io/badge/Direct%20connection-On-111827" />
  <img src="https://img.shields.io/badge/License-MIT-6b7280" />
</p>

<p><strong>A command-line tool for monitoring and handling XMU Tronclass rollcalls</strong></p>

<p>
  <strong>🇺🇸 English</strong>
  ·
  <a href="./README.zh-CN.md">🇨🇳 简体中文</a>
</p>

</div>

---

## Disclaimer

This project is provided for learning, research, and personal automation convenience only. Users are responsible for complying with their school's rules, course policies, platform terms, and applicable laws.

The author and maintainers assume no liability for account risks, data issues, platform restrictions, or any other consequences arising from use of this project.

## Overview

XMU Rollcall Bot is a Python CLI tool for logging into Xiamen University's Tronclass platform, monitoring rollcalls, and optionally forwarding new-rollcall alerts through a decoupled Hermes notification helper.

## Installation

```bash
git clone https://github.com/dangzitou/xmu-rollcall-bot.git
cd xmu-rollcall-bot
python -m pip install -e ./xmu-rollcall-cli
```

Verify the CLI:

```bash
xmu --help
```

If `xmu` is not on your PATH:

```bash
python -m xmu_rollcall.cli --help
```

## Run

### macOS / Linux

```bash
cd xmu-rollcall-bot
python3 -m pip install -e ./xmu-rollcall-cli

xmu config
xmu start
```

Fallback:

```bash
python3 -m xmu_rollcall.cli config
python3 -m xmu_rollcall.cli start
```

### Windows PowerShell

```powershell
cd C:\path\to\xmu-rollcall-bot
python -m pip install -e .\xmu-rollcall-cli

xmu config
xmu start
```

Fallback:

```powershell
python -m xmu_rollcall.cli config
python -m xmu_rollcall.cli start
```

## Commands

```bash
xmu config   # Add/delete accounts and configure rollcall safety settings or notification delivery
xmu switch   # Switch account
xmu start    # Start rollcall monitoring
xmu refresh  # Remove cached login cookies
xmu --help   # Show help
```

## Notification Architecture

New-rollcall alerts are implemented in a deployment-friendly, decoupled way:

1. `xmu_rollcall.rollcall_handler` detects a new rollcall.
2. `xmu_rollcall.events.notify_new_rollcall()` renders a notification payload.
3. `scripts/send_rollcall_notification.py` bridges into Hermes.
4. Hermes `send_message_tool` delivers to the configured chat target.

This separation keeps platform-specific delivery code out of the core monitoring loop and keeps notification targets configurable per deployment.

## Reproducible Notification Setup

### 1. Configure account-level notification behavior

Run:

```bash
xmu config
```

Choose `m` to configure notification delivery for an account, then set:

- notifications enabled = yes
- notify on new rollcall = yes
- target mode = `env`
- target value = `XMU_ROLLCALL_NOTIFY_TARGET`

Using `env` mode is recommended because it keeps `config.json` portable across environments.

### 2. Set the runtime delivery target

Example for QQBot private delivery:

```bash
export XMU_ROLLCALL_NOTIFY_TARGET="qqbot:YOUR_QQ_OPENID"
```

### 3. Start the monitor in the same environment

```bash
xmu start
```

If a new rollcall appears, the CLI will attempt to send a message immediately.

## Helper Script Contract

The helper accepts one JSON argument:

```bash
python scripts/send_rollcall_notification.py '{"target":"qqbot:YOUR_QQ_OPENID","message":"hello"}'
```

Current implementation notes:

- `qqbot:<openid>` is normalized into Hermes' QQBot home-channel flow.
- The rollcall CLI itself does not need to know QQBot REST endpoint details.
- Failures in notification delivery are reported locally without crashing the monitor loop.

## Deployment Notes

- `scripts/send_rollcall_notification.py` currently expects a local Hermes checkout at `~/.hermes/hermes-agent` by default.
- Override the Hermes checkout path with `XMU_ROLLCALL_HERMES_REPO` if your deployment stores Hermes elsewhere.
- Hermes must already be configured for the target platform before you start the rollcall monitor.
- For reproducible deployments, avoid baking target chat IDs directly into repo-tracked config files.

## Notes

- QR code rollcalls are not supported.
- Number and radar rollcall answers can be delayed, and manual confirmation can be enabled from `xmu config`.
- The tool depends on XMU/Tronclass API behavior and may break if upstream services change.
- Use it responsibly and follow your school's rules.

## License

MIT
# Daily maintenance - 2026-06-15
