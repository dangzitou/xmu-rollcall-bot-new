"""Notification data models for rollcall alerts."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time


@dataclass(frozen=True)
class NotificationTarget:
    target_type: str
    value: str

    @classmethod
    def from_value(cls, value: str) -> "NotificationTarget":
        return cls(target_type="fixed", value=value)

    @classmethod
    def from_env_name(cls, env_name: str) -> "NotificationTarget":
        return cls(target_type="env", value=env_name)

    def resolve(self) -> str | None:
        if self.target_type == "fixed":
            return self.value.strip() or None
        if self.target_type == "env":
            return os.environ.get(self.value, "").strip() or None
        return None


@dataclass(frozen=True)
class NotificationMessage:
    title: str
    lines: tuple[str, ...]

    @classmethod
    def from_rollcall(cls, account_name: str, rollcall: dict, detected_at: float | None = None) -> "NotificationMessage":
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
        return "\n".join((self.title, *self.lines))


def describe_rollcall_type(rollcall: dict) -> str:
    if rollcall.get("is_radar"):
        return "Radar rollcall"
    if rollcall.get("is_number"):
        return "Number rollcall"
    return "QRcode rollcall"
