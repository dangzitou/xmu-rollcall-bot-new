import importlib


def test_clear_screen_skips_when_not_interactive(monkeypatch):
    utils = importlib.import_module("xmu_rollcall.utils")
    calls = []

    monkeypatch.setattr(utils, "supports_interactive_terminal", lambda: False)
    monkeypatch.setattr(utils.os, "system", lambda cmd: calls.append(cmd))

    utils.clear_screen()

    assert calls == []


def test_clear_screen_uses_clear_when_interactive(monkeypatch):
    utils = importlib.import_module("xmu_rollcall.utils")
    calls = []

    monkeypatch.setattr(utils, "supports_interactive_terminal", lambda: True)
    monkeypatch.setattr(utils.os, "name", "posix")
    monkeypatch.setattr(utils.os, "system", lambda cmd: calls.append(cmd))

    utils.clear_screen()

    assert calls == ["clear"]


def test_monitor_disables_interactive_updates_without_tty():
    monitor = importlib.import_module("xmu_rollcall.monitor")
    assert monitor.INTERACTIVE_TTY is False


def test_log_heartbeat_prints_in_non_interactive_mode(monkeypatch, capsys):
    monitor = importlib.import_module("xmu_rollcall.monitor")
    monkeypatch.setattr(monitor, "INTERACTIVE_TTY", False)

    monitor.log_heartbeat("2026-05-01 02:30:00", "10s", 10)

    captured = capsys.readouterr()
    assert "HEARTBEAT" in captured.out
    assert "Current Time: 2026-05-01 02:30:00" in captured.out
    assert "Running Time: 10s" in captured.out
    assert "Query Count: 10" in captured.out


def test_log_heartbeat_skips_in_interactive_mode(monkeypatch, capsys):
    monitor = importlib.import_module("xmu_rollcall.monitor")
    monkeypatch.setattr(monitor, "INTERACTIVE_TTY", True)

    monitor.log_heartbeat("2026-05-01 02:30:00", "10s", 10)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_daytime_heartbeat_interval_is_5_minutes():
    monitor = importlib.import_module("xmu_rollcall.monitor")

    assert monitor.get_heartbeat_interval_for_hour_minute(7, 0) == 300
    assert monitor.get_heartbeat_interval_for_hour_minute(12, 0) == 300
    assert monitor.get_heartbeat_interval_for_hour_minute(18, 29) == 300


def test_nighttime_heartbeat_interval_is_1_hour():
    monitor = importlib.import_module("xmu_rollcall.monitor")

    assert monitor.get_heartbeat_interval_for_hour_minute(6, 59) == 3600
    assert monitor.get_heartbeat_interval_for_hour_minute(18, 30) == 3600
    assert monitor.get_heartbeat_interval_for_hour_minute(23, 0) == 3600
    assert monitor.get_heartbeat_interval_for_hour_minute(2, 0) == 3600
