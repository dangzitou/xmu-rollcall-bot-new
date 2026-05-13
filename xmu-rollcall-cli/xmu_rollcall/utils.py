import os
import json
import requests

import time as _time

def retry_request(fn, max_attempts=3, delay=2, backoff=2, label="request"):
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



def supports_interactive_terminal() -> bool:
    """Return True when stdout/stderr are attached to a real terminal."""
    try:
        return bool(os.environ.get("TERM")) and os.isatty(1) and os.isatty(2)
    except Exception:
        return False

base_url = "https://lnt.xmu.edu.cn"
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://ids.xmu.edu.cn/authserver/login",
}

def clear_screen():
    """清屏"""
    if not supports_interactive_terminal():
        return
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def save_session(sess: requests.Session, path: str):
    """保存session到文件"""
    try:
        cj_dict = requests.utils.dict_from_cookiejar(sess.cookies)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cj_dict, f)
    except Exception:
        pass

def load_session(sess: requests.Session, path: str):
    """从文件加载session"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cj_dict = json.load(f)
        sess.cookies = requests.utils.cookiejar_from_dict(cj_dict)
        return True
    except Exception:
        return False

def verify_session(sess: requests.Session) -> dict:
    """验证session是否有效"""
    try:
        resp = sess.get(f"{base_url}/api/profile", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "name" in data:
                return data
    except Exception:
        pass
    return {}

