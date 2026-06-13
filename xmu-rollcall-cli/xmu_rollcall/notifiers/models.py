"""Notification data models for rollcall alerts."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time


@dataclass(frozen=True)
class NotificationTarget:
    """Represents a notification delivery target.

    A target can be either a *fixed* value (e.g. a chat-id or webhook URL)
    or an *env* reference whose actual value is resolved at runtime from
    an environment variable.

    Attributes:
        target_type: Either ``"fixed"`` or ``"env"``.
        value: The fixed value itself, or the environment variable name.
    """

    target_type: str
    value: str

    @classmethod
    def from_value(cls, value: str) -> "NotificationTarget":
        """Create a target with a fixed value (e.g. a chat-id)."""
        return cls(target_type="fixed", value=value)

    @classmethod
    def from_env_name(cls, env_name: str) -> "NotificationTarget":
        """Create a target whose value is read from an environment variable."""
        return cls(target_type="env", value=env_name)

    def resolve(self) -> str | None:
        """Resolve the effective target string.

        Returns:
            The resolved string, or ``None`` if the value is empty or
            the environment variable is unset.
        """
        if self.target_type == "fixed":
            return self.value.strip() or None
        if self.target_type == "env":
            return os.environ.get(self.value, "").strip() or None
        return None


@dataclass(frozen=True)
class NotificationMessage:
    """A structured notification message for rollcall alerts.

    Attributes:
        title: The message header (e.g. ``"[XMU Rollcall Alert]"``).
        lines: Body lines of the notification.
    """

    title: str
    lines: tuple[str, ...]

    @classmethod
    def from_rollcall(cls, account_name: str, rollcall: dict, detected_at: float | None = None) -> "NotificationMessage":
        """Build a notification message from a rollcall event dict.

        Extracts teacher, course, department, rollcall type, and optional
        number code from the raw event payload and formats them into a
        structured :class:`NotificationMessage`.

        Args:
            account_name: Display name of the account that detected the event.
            rollcall: Raw rollcall event dictionary from the Tronclass API.
            detected_at: Unix timestamp of detection; defaults to now.

        Returns:
            A frozen :class:`NotificationMessage` ready for delivery.
        """
        detected_at = time.time() if detected_at is None else detected_at
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(detected_at))
        account_display = account_name or "(unknown account)"
        teacher = rollcall.get("created_by_name") or "Unknown"
        department = rollcall.get("department_name") or "Unknown department"
        course = rollcall.get("course_title") or "Unknown course"
        rollcall_id = rollcall.get("rollcall_id", "?")
        status = rollcall.get("status") or "unknown"
        number_code = rollcall.get("number_code")

        lines = [
            f"Account: {account_display}",
            f"Course: {course}",
            f"Teacher: {department} {teacher}",
            f"Type: {describe_rollcall_type(rollcall)}",
            f"Status: {status}",
            f"Rollcall ID: {rollcall_id}",
        ]
        if number_code:
            lines.append(f"签到码: {number_code}")
        lines.append(f"Detected at: {timestamp}")

        return cls(
            title="[XMU Rollcall Alert]",
            lines=tuple(lines),
        )

    def render_text(self) -> str:
        """Render the notification as a plain-text string.

        Returns:
            Title and body lines joined by newlines, suitable for
            text-based notification channels.
        """
        return "\n".join((self.title, *self.lines))


def describe_rollcall_type(rollcall: dict) -> str:
    """Return a human-readable label for the rollcall detection method.

    Args:
        rollcall: Rollcall event dictionary, expected to contain boolean
            flags ``is_radar`` and ``is_number``.

    Returns:
        One of ``"Radar rollcall"``, ``"Number rollcall"``, or
        ``"QRcode rollcall"``.
    """
    if rollcall.get("is_radar"):
        return "Radar rollcall"
    if rollcall.get("is_number"):
        return "Number rollcall"
    return "QRcode rollcall"
