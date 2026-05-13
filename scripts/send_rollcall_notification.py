#!/usr/bin/env python3
"""Send a rollcall notification through Hermes send_message internals.

Usage:
  python scripts/send_rollcall_notification.py '{"target": "qqbot:...", "message": "..."}'
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


HERMES_REPO = Path(
    os.environ.get("XMU_ROLLCALL_HERMES_REPO", str(Path.home() / ".hermes" / "hermes-agent"))
).expanduser()
HERMES_HOME = Path.home() / ".hermes"


def _load_hermes_send_message_tool():
    if str(HERMES_REPO) not in sys.path:
        sys.path.insert(0, str(HERMES_REPO))

    from hermes_cli.env_loader import load_hermes_dotenv

    load_hermes_dotenv(hermes_home=HERMES_HOME, project_env=HERMES_REPO / ".env")

    from tools.send_message_tool import send_message_tool

    return send_message_tool


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    previous: dict[str, str | None] = {}
    try:
        for key, value in overrides.items():
            previous[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _normalize_target_for_send(target: str) -> tuple[str, dict[str, str]]:
    platform, sep, rest = target.partition(":")
    platform = platform.strip().lower()
    explicit_id = rest.strip() if sep else ""

    if platform == "qqbot" and explicit_id:
        return "qqbot", {"QQBOT_HOME_CHANNEL": explicit_id}

    return target, {}


def main() -> int:
    if len(sys.argv) != 2:
        print("Expected exactly one JSON payload argument", file=sys.stderr)
        return 2

    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON payload: {exc}", file=sys.stderr)
        return 2

    target = str(payload.get("target", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not target or not message:
        print("Payload must include non-empty target and message", file=sys.stderr)
        return 2

    send_target, env_overrides = _normalize_target_for_send(target)
    send_message_tool = _load_hermes_send_message_tool()
    with _temporary_env(env_overrides):
        result = send_message_tool({"action": "send", "target": send_target, "message": message})

    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError:
        parsed = {"raw": str(result)}

    if isinstance(parsed, dict) and parsed.get("error"):
        print(parsed["error"], file=sys.stderr)
        return 1

    output = {
        "requested_target": target,
        "send_target": send_target,
        "env_overrides": sorted(env_overrides.keys()),
        "result": parsed,
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
