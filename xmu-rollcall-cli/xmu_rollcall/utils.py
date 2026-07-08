"""Utility helpers: HTTP retries, session persistence, and terminal helpers."""

import os
import json
from typing import Any, Callable, TypeVar

import requests
import time as _time

T = TypeVar("T")

def retry_request(fn: Callable[[], T], max_attempts: int = 3, delay: float = 2, backoff: float = 2, label: str = "request") -> T:
    """Retry a callable with exponential backoff.

    Args:
        fn: Zero-arg callable that performs the request and returns a response.
        max_attempts: Maximum number of attempts (default 3).
        delay: Initial delay between retries in seconds (default 2).
        backoff: Multiplier applied to delay after each retry (default 2).
        label: Human-readable label for log messages.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception after all attempts exhausted.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < max_attempts:
                _time.sleep(delay)
                delay *= backoff
    raise last_exc



def format_duration(seconds: float) -> str:
    """Format a duration in seconds into a human-readable Chinese string.

    Examples::

        format_duration(90)   → "1分30秒"
        format_duration(3661) → "1小时1分1秒"
        format_duration(45)   → "45秒"

    Args:
        seconds: Duration in seconds (non-negative).

    Returns:
        A human-readable string with appropriate units.
    """
    if seconds < 0:
        seconds = 0
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}秒"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}分{secs}秒" if secs else f"{minutes}分"
    hours, minutes = divmod(minutes, 60)
    parts = [f"{hours}小时"]
    if minutes:
        parts.append(f"{minutes}分")
    if secs:
        parts.append(f"{secs}秒")
    return "".join(parts)


def supports_interactive_terminal() -> bool:
    """Return True when stdout/stderr are attached to a real terminal."""
    try:
        return bool(os.environ.get("TERM")) and os.isatty(1) and os.isatty(2)
    except Exception:
        return False

BASE_URL: str = "https://lnt.xmu.edu.cn"
"""XMU campus life-service base URL."""

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://ids.xmu.edu.cn/authserver/login",
}
"""Default HTTP headers mimicking a standard Chrome browser."""

def clear_screen() -> None:
    """Clear the terminal screen.

    No-op when stdout is not attached to an interactive terminal.
    Uses ``cls`` on Windows and ``clear`` on POSIX systems.
    """
    if not supports_interactive_terminal():
        return
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def save_session(sess: requests.Session, path: str) -> None:
    """Persist a session's cookies to a JSON file.

    Args:
        sess: The :class:`requests.Session` whose cookies to save.
        path: Destination file path (will be overwritten).
    """
    try:
        cj_dict = requests.utils.dict_from_cookiejar(sess.cookies)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cj_dict, f)
    except Exception:
        pass

def load_session(sess: requests.Session, path: str) -> bool:
    """Restore a session's cookies from a previously saved JSON file.

    Args:
        sess: The :class:`requests.Session` to restore cookies into.
        path: Path to the JSON cookie file.

    Returns:
        ``True`` on success, ``False`` if the file is missing or corrupt.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            cj_dict = json.load(f)
        sess.cookies = requests.utils.cookiejar_from_dict(cj_dict)
        return True
    except Exception:
        return False

def verify_session(sess: requests.Session) -> dict[str, Any]:
    """Check whether a session is still authenticated.

    Makes a GET request to ``/api/profile`` and returns the parsed JSON
    if it contains a ``name`` key.

    Args:
        sess: An authenticated :class:`requests.Session`.

    Returns:
        The profile dict on success, or an empty dict on failure.
    """
    try:
        resp = sess.get(f"{BASE_URL}/api/profile", headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "name" in data:
                return data
    except Exception:
        pass
    return {}


# Backward-compatible aliases (deprecated — use UPPER_CASE versions)
base_url = BASE_URL
headers = HEADERS

