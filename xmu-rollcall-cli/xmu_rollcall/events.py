"""Event helpers for rollcall notifications."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .notifiers.models import NotificationMessage
from .notifications_config import get_notification_target, normalize_notifications_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEND_HELPER = PROJECT_ROOT / "scripts" / "send_rollcall_notification.py"


class NotificationError(RuntimeError):
    """Raised when a notification could not be delivered."""


def notify_new_rollcall(account: dict, rollcall: dict) -> bool:
    notifications = normalize_notifications_config(account.get("notifications"))
    if not notifications.get("enabled") or not notifications.get("notify_on_new_rollcall"):
        return False

    target = get_notification_target(notifications)
    resolved_target = target.resolve()
    if not resolved_target:
        env_hint = target.value if target.target_type == "env" else "(fixed target)"
        print(f"Notification skipped: target is not configured ({env_hint}).")
        return False

    message = NotificationMessage.from_rollcall(
        account_name=account.get("name") or account.get("username") or "",
        rollcall=rollcall,
    )
    payload = {
        "target": resolved_target,
        "message": message.render_text(),
    }
    run_notification_command(payload)
    return True


def run_notification_command(payload: dict) -> None:
    if not SEND_HELPER.exists():
        raise NotificationError(f"Notification helper script not found: {SEND_HELPER}")

    command = [sys.executable, str(SEND_HELPER), json.dumps(payload, ensure_ascii=False)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "unknown error").strip()
        raise NotificationError(f"Failed to deliver notification: {stderr}")
