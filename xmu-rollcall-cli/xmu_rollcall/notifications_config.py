"""Notification target configuration helpers."""

from __future__ import annotations

from .notifiers.models import NotificationTarget

DEFAULT_NOTIFICATION_TARGET_ENV = "XMU_ROLLCALL_NOTIFY_TARGET"


def default_notifications_config() -> dict:
    return {
        "enabled": False,
        "target": {
            "type": "env",
            "value": DEFAULT_NOTIFICATION_TARGET_ENV,
        },
        "notify_on_new_rollcall": True,
    }


def normalize_notifications_config(config: dict | None) -> dict:
    merged = default_notifications_config()
    target = (config or {}).get("target") or {}
    merged.update({
        "enabled": bool((config or {}).get("enabled", merged["enabled"])),
        "notify_on_new_rollcall": bool((config or {}).get("notify_on_new_rollcall", merged["notify_on_new_rollcall"])),
    })
    merged["target"] = {
        "type": target.get("type", merged["target"]["type"]),
        "value": str(target.get("value", merged["target"]["value"])).strip() or merged["target"]["value"],
    }
    return merged


def get_notification_target(notifications_config: dict | None) -> NotificationTarget:
    config = normalize_notifications_config(notifications_config)
    target = config["target"]
    if target["type"] == "fixed":
        return NotificationTarget.from_value(target["value"])
    return NotificationTarget.from_env_name(target["value"])
