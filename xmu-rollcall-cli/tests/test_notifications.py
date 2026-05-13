import time

from xmu_rollcall import events
from xmu_rollcall.notifiers.models import NotificationMessage, NotificationTarget


def test_notification_target_from_env_name():
    target = NotificationTarget.from_env_name("XMU_NOTIFY_TARGET")

    assert target.target_type == "env"
    assert target.value == "XMU_NOTIFY_TARGET"


def test_notification_target_from_fixed_target():
    target = NotificationTarget.from_value("qqbot:demo-user")

    assert target.target_type == "fixed"
    assert target.value == "qqbot:demo-user"


def test_build_rollcall_message_contains_core_fields():
    now = 1712345678
    message = NotificationMessage.from_rollcall(
        account_name="Alice",
        rollcall={
            "course_title": "Linear Algebra",
            "created_by_name": "Prof. Chen",
            "department_name": "Math Dept",
            "rollcall_id": 42,
            "status": "absent",
            "is_radar": False,
            "is_number": True,
        },
        detected_at=now,
    )

    text = message.render_text()
    assert "Linear Algebra" in text
    assert "Prof. Chen" in text
    assert "Number rollcall" in text
    assert "Alice" in text
    assert "42" in text
    assert time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) in text


def test_build_rollcall_message_uses_qrcode_for_other_types():
    message = NotificationMessage.from_rollcall(
        account_name="",
        rollcall={
            "course_title": "PE",
            "created_by_name": "Coach Li",
            "department_name": "Sports",
            "rollcall_id": 7,
            "status": "absent",
            "is_radar": False,
            "is_number": False,
        },
        detected_at=1712345678,
    )

    assert "QRcode rollcall" in message.render_text()


def test_notify_new_rollcall_dispatches_rendered_payload(monkeypatch):
    captured = {}

    def fake_run_notification_command(payload):
        captured["payload"] = payload

    monkeypatch.setattr(events, "run_notification_command", fake_run_notification_command)

    account = {
        "name": "Alice",
        "notifications": {
            "enabled": True,
            "notify_on_new_rollcall": True,
            "target": {"type": "fixed", "value": "qqbot:demo-user"},
        },
    }
    rollcall = {
        "course_title": "Linear Algebra",
        "created_by_name": "Prof. Chen",
        "department_name": "Math Dept",
        "rollcall_id": 42,
        "status": "active",
        "is_number": True,
    }

    delivered = events.notify_new_rollcall(account, rollcall)

    assert delivered is True
    assert captured["payload"]["target"] == "qqbot:demo-user"
    assert captured["payload"]["message"].startswith("[XMU Rollcall Alert]")
    assert "Linear Algebra" in captured["payload"]["message"]
    assert "Prof. Chen" in captured["payload"]["message"]
    assert "Number rollcall" in captured["payload"]["message"]


def test_notify_new_rollcall_skips_when_notifications_disabled(monkeypatch):
    called = False

    def fake_run_notification_command(payload):
        nonlocal called
        called = True

    monkeypatch.setattr(events, "run_notification_command", fake_run_notification_command)

    delivered = events.notify_new_rollcall(
        {
            "name": "Alice",
            "notifications": {"enabled": False},
        },
        {"course_title": "Ignored"},
    )

    assert delivered is False
    assert called is False
