"""Rollcall detection, processing and auto-answering logic.

This module provides the core handler that processes incoming rollcall
detections, determines their type (QR code / number / radar), waits
for the configured delay or classmate threshold, and dispatches the
appropriate sign-in action.
"""

from __future__ import annotations

import time
import random

import requests

from .config import get_rollcall_settings
from .verify import send_code, send_radar
from .events import notify_new_rollcall

WAIT_POLL_INTERVAL = 3
WAIT_FOR_CLASSMATES_TIMEOUT = 120

_SIGNED_FIELDS = (
    'course_title', 'created_by_name', 'department_name',
    'is_expired', 'is_number', 'is_radar',
    'rollcall_id', 'rollcall_status', 'scored', 'status',
)

_SIGNED_STATUSES = {'on_call_fine'}


def _fetch_signed_count(session: requests.Session, rollcall_id: int) -> int | None:
    """Query the API for the number of students who have already signed in.

    Args:
        session: Authenticated requests session with valid cookies.
        rollcall_id: The rollcall event ID to query.

    Returns:
        The count of students who have answered, or ``None`` if the
        request fails.
    """
    try:
        from .utils import BASE_URL
        resp = session.get(
            f"{BASE_URL}/api/rollcall/{rollcall_id}/student_rollcalls",
            timeout=10,
        )
        if resp.status_code == 200:
            students = resp.json().get("student_rollcalls", [])
            return sum(1 for s in students if s.get("updated_at"))
    except Exception:
        pass
    return None

def wait_for_classmates(session: requests.Session, rollcall_id: int, settings: dict) -> None:
    """根据配置等待足够多的同学签到后再签，最多等待120秒。

    Args:
        session: 已认证的 requests 会话。
        rollcall_id: 签到事件 ID。
        settings: 签到设置字典，包含 ``wait_before_answer_mode`` 等字段。
    """
    mode = settings.get("wait_before_answer_mode", "none")
    if mode == "none":
        return

    if mode == "fixed":
        target = settings.get("wait_before_answer_count_min", 0)
    elif mode == "random":
        lo = settings.get("wait_before_answer_count_min", 0)
        hi = settings.get("wait_before_answer_count_max", 0)
        target = random.randint(lo, hi) if hi > lo else lo
    else:
        return

    if target <= 0:
        return

    print(f"Waiting for {target} classmate(s) to answer before signing...")
    deadline = time.monotonic() + WAIT_FOR_CLASSMATES_TIMEOUT
    while time.monotonic() < deadline:
        count = _fetch_signed_count(session, rollcall_id)
        if count is not None:
            print(f"\r  Signed: {count}/{target}", end="", flush=True)
            if count >= target:
                print()
                return
        time.sleep(WAIT_POLL_INTERVAL)
    print(f"\nTimeout after {WAIT_FOR_CLASSMATES_TIMEOUT}s, proceeding anyway.")

def process_rollcalls(data: dict, session: requests.Session, account: dict | None = None) -> dict:
    """处理签到数据，区分 QRcode 需手动处理和真正失败。"""
    result = handle_rollcalls(data, session, account)
    rollcalls = data.get('rollcalls', [])

    # 如果所有签到都已处理（包括已签到、QRcode手动处理），返回原数据；
    # 只有在真正失败（send_code/send_radar 返回 False）时才返回空数据。
    has_real_failure = False
    for i, rc in enumerate(rollcalls):
        if not result[i] and not (rc.get('is_radar') is False and rc.get('is_number') is False):
            has_real_failure = True
            break

    if has_real_failure:
        return {'rollcalls': []}
    return data

def extract_rollcalls(data: dict) -> tuple[int, list[dict]]:
    """Extract and normalise rollcall entries from raw API data.

    Args:
        data: Raw API response containing a ``rollcalls`` list.

    Returns:
        A tuple of (count, normalised_rollcall_dicts).
    """
    rollcalls = data.get('rollcalls', [])
    result = [
        {field: rc[field] for field in _SIGNED_FIELDS}
        for rc in rollcalls
    ]
    return len(rollcalls), result

def _wait_with_countdown(delay_min: int, delay_max: int, label: str) -> None:
    """Sleep for a random delay in [delay_min, delay_max] with a live countdown.

    Args:
        delay_min: Minimum delay in seconds.
        delay_max: Maximum delay in seconds (must be >= delay_min for randomness).
        label: Human-readable rollcall type for status messages (e.g. "number", "radar").
    """
    delay = random.randint(delay_min, delay_max) if delay_max > delay_min else delay_min

    if delay <= 0:
        return

    print(f"Waiting {delay} second(s) before answering {label} rollcall...")
    for remaining in range(delay, 0, -1):
        print(f"\rAnswering in {remaining:>3}s. Press Ctrl+C to cancel.", end="", flush=True)
        time.sleep(1)
    print()


def wait_before_number_answer(settings: dict) -> None:
    """Sleep for a random delay before answering a number rollcall."""
    _wait_with_countdown(settings["number_delay_min"], settings["number_delay_max"], "number")

def wait_before_radar_answer(settings: dict) -> None:
    """Sleep for a random delay before answering a radar rollcall."""
    _wait_with_countdown(settings.get("radar_delay_min", 0), settings.get("radar_delay_max", 0), "radar")

def confirm_before_answer(settings: dict) -> bool:
    """Prompt the user for confirmation before answering, if manual mode is on."""
    if not settings["manual_confirm"]:
        return True

    answer = input("Answer this rollcall now? [y/N]: ").strip().lower()
    return answer == "y"

def handle_rollcalls(data: dict, session: requests.Session, account: dict | None = None) -> list[bool]:
    """Process each rollcall entry: detect type, apply delays, and sign in.

    Args:
        data: Raw API response containing a ``rollcalls`` list.
        session: Authenticated HTTP session.
        account: Optional account configuration dict for notifications.

    Returns:
        A list of booleans indicating success for each rollcall entry.
    """
    count, rollcalls = extract_rollcalls(data)
    answer_status = [False] * count
    settings = get_rollcall_settings(account or {})

    if count:
        print(time.strftime("%H:%M:%S", time.localtime()), f"New rollcall(s) found!\n")
        for i in range(count):
            rc = rollcalls[i]
            print(f"{i+1} of {count}:")
            print(f"Course name: {rc['course_title']}, rollcall created by {rc['department_name']} {rc['created_by_name']}.")

            if rc['is_radar']:
                rollcall_type = "Radar rollcall"
            elif rc['is_number']:
                rollcall_type = "Number rollcall"
            else:
                rollcall_type = "QRcode rollcall"
            print(f"Rollcall type: {rollcall_type}\n")

            # Send notification
            if account:
                try:
                    notify_new_rollcall(account, rc)
                except Exception as e:
                    print(f"Notification error: {e}")

            already_signed = rc['status'] in _SIGNED_STATUSES
            if already_signed:
                print("Already answered.")
                answer_status[i] = True
            elif rc['is_number'] and not rc['is_radar']:
                wait_before_number_answer(settings)
                wait_for_classmates(session, rc['rollcall_id'], settings)
                if send_code(session, rc['rollcall_id']):
                    answer_status[i] = True
                else:
                    print("Answering failed.")
            elif rc['is_radar']:
                wait_before_radar_answer(settings)
                wait_for_classmates(session, rc['rollcall_id'], settings)
                if send_radar(session, rc['rollcall_id']):
                    answer_status[i] = True
                else:
                    print("Answering failed.")
            else:
                # QRcode rollcall - 无法自动处理，仅通知
                print("QRcode rollcall - please scan the QR code manually.")

    return answer_status
