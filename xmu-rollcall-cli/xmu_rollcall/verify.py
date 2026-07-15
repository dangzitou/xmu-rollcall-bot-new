"""Rollcall answer strategies: number-code and radar (location-based) sign-in.

This module provides the two main rollcall verification paths:

- :func:`send_code` — fetches a number code from the API and submits it.
- :func:`send_radar` — uses two probe locations and trilateration to answer
  location-based rollcalls when the exact sign-in position is unknown.
"""

from __future__ import annotations

import uuid
import time
import math
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

def send_code(in_session: requests.Session, rollcall_id: int) -> bool:
    """Answer a number-code rollcall by fetching the code from the API.

    Args:
        in_session: Authenticated requests session with valid cookies.
        rollcall_id: The rollcall event ID to answer.

    Returns:
        True if the rollcall was answered successfully, False otherwise.
    """
    code_url = f"{BASE_URL}/api/rollcall/{rollcall_id}/student_rollcalls"
    answer_url = f"{BASE_URL}/api/rollcall/{rollcall_id}/answer_number_rollcall"
    print("Trying number code from API...")
    t00 = time.time()
    request_headers = in_session.headers
    try:
        code_response = retry_request(
            lambda: in_session.get(code_url, headers=request_headers, timeout=15),
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

    number_code = find_number_code(code_data)
    if not number_code:
        t01 = time.time()
        print(f"Failed to get number code. 'number_code' not found in API response.\nTime: {t01 - t00:.2f} s.")
        return False

    payload = {
        "deviceId": str(uuid.uuid4()),
        "numberCode": number_code
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

def send_radar(in_session: requests.Session, rollcall_id: int) -> bool:
    """Answer a radar (location-based) rollcall using trilateration.

    Attempts two probe locations first; if neither is within range,
    uses the reported distances to trilaterate the actual sign-in
    location and retries with the computed coordinates.

    Args:
        in_session: Authenticated requests session with valid cookies.
        rollcall_id: The rollcall event ID to answer.

    Returns:
        True if the rollcall was answered successfully, False otherwise.
    """
    url = f"{BASE_URL}/api/rollcall/{rollcall_id}/answer"

    lat_1, lat_2 = 24.3, 24.6
    lon_1, lon_2 = 118.0, 118.2

    def payload(lat: float, lon: float) -> dict:
        """Build a radar answer payload for the given coordinates."""
        return {
            "accuracy": 35,
            "altitude": 0,
            "altitudeAccuracy": None,
            "deviceId": str(uuid.uuid4()),
            "heading": None,
            "latitude": lat,
            "longitude": lon,
            "speed": None
        }

    res_1 = retry_request(
        lambda: in_session.put(url, json=payload(lat_1, lon_1), headers=HEADERS, timeout=15),
        max_attempts=3, delay=2, label="radar_1",
    )
    data_1 = res_1.json()

    if res_1.status_code == 200:
        return True

    res_2 = retry_request(
        lambda: in_session.put(url, json=payload(lat_2, lon_2), headers=HEADERS, timeout=15),
        max_attempts=3, delay=2, label="radar_2",
    )
    data_2 = res_2.json()

    if res_2.status_code == 200:
        return True

    distance_1 = data_1.get("distance")
    distance_2 = data_2.get("distance")

    if distance_1 is None or distance_2 is None:
        print(f"Radar sign-in failed: server did not return distance info. "
              f"distance_1={distance_1}, distance_2={distance_2}")
        return False

    def latlon_to_xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
        """Convert lat/lon to local x/y meters relative to a reference point."""
        R = 6371000
        x = math.radians(lon - lon0) * R * math.cos(math.radians(lat0))
        y = math.radians(lat - lat0) * R
        return x, y

    def xy_to_latlon(x: float, y: float, lat0: float, lon0: float) -> tuple[float, float]:
        """Convert local x/y meters back to lat/lon relative to a reference point."""
        R = 6371000
        lat = lat0 + math.degrees(y / R)
        lon = lon0 + math.degrees(x / (R * math.cos(math.radians(lat0))))
        return lat, lon

    def circle_intersections(x1: float, y1: float, d1: float, x2: float, y2: float, d2: float) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """Return the two intersection points of two circles, or None if they don't intersect."""
        D = math.hypot(x2 - x1, y2 - y1)

        if D > d1 + d2 or D < abs(d1 - d2):
            return None

        a = (d1**2 - d2**2 + D**2) / (2 * D)
        h = math.sqrt(d1**2 - a**2)

        xm = x1 + a * (x2 - x1) / D
        ym = y1 + a * (y2 - y1) / D

        rx = -(y2 - y1) * (h / D)
        ry = (x2 - x1) * (h / D)

        p1 = (xm + rx, ym + ry)
        p2 = (xm - rx, ym - ry)
        return p1, p2

    def solve_two_points(lat1: float, lon1: float, lat2: float, lon2: float, d1: float, d2: float) -> tuple[tuple[float, float], tuple[float, float]] | None:
        """Trilaterate two candidate lat/lon positions from two reference points and their distances."""
        lat0 = (lat1 + lat2) / 2
        lon0 = (lon1 + lon2) / 2
        x1, y1 = latlon_to_xy(lat1, lon1, lat0, lon0)
        x2, y2 = latlon_to_xy(lat2, lon2, lat0, lon0)

        sols = circle_intersections(x1, y1, d1, x2, y2, d2)
        if sols is None:
            return None

        p1 = xy_to_latlon(sols[0][0], sols[0][1], lat0, lon0)
        p2 = xy_to_latlon(sols[1][0], sols[1][1], lat0, lon0)
        return p1, p2

    resolutions = solve_two_points(lat_1, lon_1, lat_2, lon_2, distance_1, distance_2)
    if resolutions:
        ((sol_x_1, sol_y_1), (sol_x_2, sol_y_2)) = resolutions
    else:
        return False

    payload_1 = payload(sol_x_1, sol_y_1)
    payload_2 = payload(sol_x_2, sol_y_2)

    try:
        res_3 = retry_request(
            lambda: in_session.put(url, json=payload_1, headers=HEADERS, timeout=15),
            max_attempts=2, delay=1, label="radar_trilat_1",
        )
        if res_3.status_code == 200:
            return True
        print(f"Radar trilateration point 1 rejected: {res_3.json()}")
    except requests.RequestException as e:
        print(f"Radar trilateration point 1 request failed: {e}")

    try:
        res_4 = retry_request(
            lambda: in_session.put(url, json=payload_2, headers=HEADERS, timeout=15),
            max_attempts=2, delay=1, label="radar_trilat_2",
        )
        if res_4.status_code == 200:
            return True
        print(f"Radar trilateration point 2 rejected: {res_4.json()}")
    except requests.RequestException as e:
        print(f"Radar trilateration point 2 request failed: {e}")

    return False
