"""Notification delivery backends.

Re-exports the core notification data models so callers can import from
``xmu_rollcall.notifiers`` directly.
"""

from .models import NotificationMessage, NotificationTarget

__all__ = ["NotificationMessage", "NotificationTarget"]
