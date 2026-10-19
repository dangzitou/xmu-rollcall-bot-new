"""Rollcall answer strategies: number-code and radar (location-based) sign-in.

This module provides the two main rollcall verification paths:

- :func:`send_code` — fetches a number code from the timetable API and submits it.
- :func:`send_radar` — submits the fixed campus position (学武楼, Xiang'an Campus).
"""

from __future__ import annotations

import uuid
import time
import json
from typing import Any

import requests
from .utils import retry_request, BASE_URL, HEADERS

def find_number_code(data: Any, depth: int = 0, max_depth: int = 10) -> str | None:
    """Extract number_code from nested dict/list API responses.

    Args:
        data: Parsed JSON payload from Tronclass APIs.
        depth: Current recursive depth when traversing nested structures.
        max_depth: Maximum depth allowed for traversal to avoid pathological recursion.

    Returns:
        str or None: The first discovered number_code value, or None if not found.
    """
    if depth > max_depth:
        return None
    if isinstance(data, dict):
        number_code = data.get("number_code")
        if number_code is not None:
            return str(number_code)
        for value in data.values():
            nested_code = find_number_code(value, depth + 1, max_depth)
            if nested_code:
                return nested_code
    elif isinstance(data, list):
        for item in data:
            nested_code = find_number_code(item, depth + 1, max_depth)
            if nested_code:
                return nested_code
    return None

def get_rollcall_detail(in_session: requests.Session, rollcall_id: int) -> dict:
    """Fetch rollcall detail (course_id, rollcall_time) from the API.

    Returns an empty dict on any failure so callers can degrade gracefully.
    """
    try:
        resp = retry_request(
            lambda: in_session.get(
                f"{BASE_URL}/api/rollcall/{rollcall_id}",
                headers=in_session.headers, timeout=15,
            ),
            max_attempts=3, delay=2, label="rollcall_detail",
        )
        if resp.status_code != 200:
            print(f"Rollcall detail HTTP {resp.status_code} for id={rollcall_id}")
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Failed to fetch rollcall detail for id={rollcall_id}: {e}")
        return {}


def send_code(in_session: requests.Session, rollcall_id: int) -> bool:
    """Answer a number-code rollcall by fetching the code from the API.

    Uses the current Tronclass flow (upstream PR alkali210/XMU-Rollcall-Bot#13):

    1. ``GET /api/rollcall/{rollcall_id}``            -> course_id, rollcall_time
    2. ``GET /api/timetable_rollcalls?course_ids=...&rollcall_date=yyyy-mm-dd``
    3. Locate the entry whose ``id`` matches rollcall_id and read ``number_code``.

    The legacy ``/api/rollcall/{id}/student_rollcalls`` endpoint no longer
    exposes ``number_code`` — it returns 200 with the field absent, which is
    why the old recursive search always failed.

    Args:
        in_session: Authenticated requests session with valid cookies.
        rollcall_id: The rollcall event ID to answer.

    Returns:
        True if the rollcall was answered successfully, False otherwise.
    """
    answer_url = f"{BASE_URL}/api/rollcall/{rollcall_id}/answer_number_rollcall"
    print("Trying number code from API...")
    t00 = time.time()
    request_headers = in_session.headers

    # --- Step 1: resolve course_id + rollcall_date ---
    detail = get_rollcall_detail(in_session, rollcall_id)
    course_id = detail.get("course_id")
    rollcall_time = detail.get("rollcall_time")
    if not course_id or not rollcall_time:
        t01 = time.time()
        print(
            "Failed to get rollcall course or time from API response. "
            f"detail_keys={sorted(detail.keys())}\nTime: {t01 - t00:.2f} s."
        )
        return False

    try:
        # The timetable API indexes by UTC date, not Beijing time. Using
        # UTC+8 here silently breaks every rollcall between 00:00 and 07:59
        # Beijing time, because the queried date lands on the previous day.
        from datetime import datetime, timezone
        rollcall_date = (
            datetime.fromisoformat(str(rollcall_time).replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .date()
            .isoformat()
        )
    except Exception as e:
        t01 = time.time()
        print(f"Failed to parse rollcall_time {rollcall_time!r}: {e}\nTime: {t01 - t00:.2f} s.")
        return False

    # --- Step 2: timetable_rollcalls ---
    timetable_url = f"{BASE_URL}/api/timetable_rollcalls"
    try:
        code_response = retry_request(
            lambda: in_session.get(
                timetable_url,
                params={"course_ids": course_id, "rollcall_date": rollcall_date},
                headers=request_headers, timeout=15,
            ),
            max_attempts=3, delay=2, label="get_number_code",
        )
        if code_response.status_code != 200:
            t01 = time.time()
            print(f"Failed to get number code. Status: {code_response.status_code}\nTime: {t01 - t00:.2f} s.")
            return False
        code_data = code_response.json()
    except requests.RequestException as e:
        t01 = time.time()
        print(f"Failed to request number code API: {e}\nTime: {t01 - t00:.2f} s.")
        return False
    except ValueError as e:
        t01 = time.time()
        print(f"Failed to parse number code API response: {e}\nTime: {t01 - t00:.2f} s.")
        return False

    # Diagnostic dump: this endpoint has changed shape before, and the raw body
    # is the only way to tell "field renamed" apart from "value is null".
    print(f"[diag] timetable_rollcalls body: {json.dumps(code_data, ensure_ascii=False)[:800]}")

    rollcalls = code_data.get("rollcalls") if isinstance(code_data, dict) else None
    if not isinstance(rollcalls, list):
        t01 = time.time()
        print(
            "Failed to get rollcalls from timetable API response "
            f"(keys={sorted(code_data.keys()) if isinstance(code_data, dict) else type(code_data).__name__}).\n"
            f"Time: {t01 - t00:.2f} s."
        )
        return False

    number_code = None
    for rollcall in rollcalls:
        if not isinstance(rollcall, dict) or str(rollcall.get("id")) != str(rollcall_id):
            continue
        number_code = rollcall.get("number_code")
        if number_code is None or str(number_code).strip() == "":
            number_code = None
        break

    if not number_code:
        t01 = time.time()
        print(
            f"Failed to get number code. 'number_code' not found in API response "
            f"(matched_id={rollcall_id}, candidates={[r.get('id') for r in rollcalls if isinstance(r, dict)]}).\n"
            f"Time: {t01 - t00:.2f} s."
        )
        return False

    payload = {
        "deviceId": str(uuid.uuid4()),
        "numberCode": str(number_code)
    }
    try:
        response = retry_request(
            lambda: in_session.put(answer_url, json=payload, headers=request_headers, timeout=15),
            max_attempts=3, delay=2, label="answer_number",
        )
        if response.status_code == 200:
            print("Number code rollcall answered successfully.\nNumber code: ", number_code)
            time.sleep(5)
            t01 = time.time()
            print(f"Time: {t01 - t00:.2f} s.")
            return True
        t01 = time.time()
        print(f"Failed to submit number code. Status: {response.status_code}\nTime: {t01 - t00:.2f} s.")
        return False
    except requests.RequestException as e:
        t01 = time.time()
        print(f"Failed to submit number code: {e}\nTime: {t01 - t00:.2f} s.")
        return False

# Fixed sign-in locations on Xiang'an Campus, Xiamen University.
# Source: Baidu Maps geocoder (ak-based geocoding/v3).
#   precise=1 / confidence=70  -> building-level match
#   precise=1 / confidence=75  -> block-level match
# Tried in order; the first accepted position wins.
RADAR_LOCATIONS = [
    # 学武楼 — building-level, confidence 70
    {"label": "学武楼", "lat": 24.611347, "lon": 118.320115},
    # 坤銮楼 — building-level, confidence 70 (adjacent to 学武楼, ~70 m apart)
    {"label": "坤銮楼", "lat": 24.611381, "lon": 118.319275},
    # 西部片区2号楼 — Baidu has no entry for the building itself, so this is the
    # "厦门大学西部片区" block centroid (comprehension=100). Coarser than the
    # first two; used only as a last resort.
    {"label": "西部片区2号楼", "lat": 24.612687, "lon": 118.307112},
]


def send_radar(in_session: requests.Session, rollcall_id: int) -> bool:
    """Answer a radar (location-based) rollcall with fixed campus positions.

    Submits coordinates for 学武楼, then 坤銮楼, then 西部片区2号楼 as a
    fallback chain, stopping at the first position the server accepts.

    The previous implementation probed two distant points and trilaterated
    from the returned distances; that was removed because the real sign-in
    location is known and constant, and the probe points (24.3/24.6 lat,
    118.0/118.2 lon) spanned all of Xiamen.

    Args:
        in_session: Authenticated requests session with valid cookies.
        rollcall_id: The rollcall event ID to answer.

    Returns:
        True if any position was accepted, False otherwise.
    """
    url = f"{BASE_URL}/api/rollcall/{rollcall_id}/answer"

    for index, loc in enumerate(RADAR_LOCATIONS, start=1):
        payload = {
            "accuracy": 35,
            "altitude": 0,
            "altitudeAccuracy": None,
            "deviceId": str(uuid.uuid4()),
            "heading": None,
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "speed": None,
        }
        print(f"Radar attempt {index}/{len(RADAR_LOCATIONS)}: "
              f"{loc['label']} ({loc['lat']}, {loc['lon']})")
        try:
            response = retry_request(
                lambda: in_session.put(url, json=payload, headers=HEADERS, timeout=15),
                max_attempts=2, delay=1, label=f"radar_answer_{index}",
            )
        except requests.RequestException as e:
            print(f"Radar request failed for {loc['label']}: {e}")
            continue

        if response.status_code == 200:
            print(f"Radar rollcall answered successfully with {loc['label']}.")
            return True

        try:
            body = response.json()
        except ValueError:
            body = response.text[:300]
        print(f"Radar rejected for {loc['label']}. "
              f"Status: {response.status_code} Body: {body}")

    print("All radar positions rejected.")
    return False
