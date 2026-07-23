"""Notification target configuration helpers."""

from __future__ import annotations

from .notifiers.models import NotificationTarget

DEFAULT_NOTIFICATION_TARGET_ENV = "XMU_ROLLCALL_NOTIFY_TARGET"


def default_notifications_config() -> dict:
    """Return the default notification configuration dict."""
    return {
        "enabled": False,
        "target": {
            "type": "env",
            "value": DEFAULT_NOTIFICATION_TARGET_ENV,
        },
        "notify_on_new_rollcall": True,
    }


def normalize_notifications_config(config: dict | None) -> dict:
    """Merge user-supplied notification config with defaults and return normalized result.

    Missing keys are filled from :func:`default_notifications_config`.  The
    nested ``target`` dict is merged separately so that a partial override
    (e.g. only ``target.type``) does not discard the other sub-keys.

    Args:
        config: Raw notification configuration from the user's account file,
            or ``None`` if no configuration was provided.

    Returns:
        A fully-populated notification configuration dict with the same
        schema as :func:`default_notifications_config`.
    """
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
    """Resolve the effective notification target from config.

    Normalizes the raw config, then builds a :class:`NotificationTarget`
    based on the ``target.type`` field:

    * ``"fixed"`` — the ``value`` is used directly as a chat-id or URL.
    * ``"env"`` (default) — the ``value`` is treated as the name of an
      environment variable that holds the actual target identifier.

    Args:
        notifications_config: Raw notification configuration dict, or
            ``None`` to fall back to defaults.

    Returns:
        A :class:`NotificationTarget` ready to be resolved via
        :meth:`~NotificationTarget.resolve`.
    """
    config = normalize_notifications_config(notifications_config)
    # Prefer .get even after normalize so hand-edited partial configs stay safe.
    target = config.get("target") or {}
    target_type = target.get("type", "env")
    target_value = str(target.get("value", DEFAULT_NOTIFICATION_TARGET_ENV)).strip() or DEFAULT_NOTIFICATION_TARGET_ENV
    if target_type == "fixed":
        return NotificationTarget.from_value(target_value)
    return NotificationTarget.from_env_name(target_value)
