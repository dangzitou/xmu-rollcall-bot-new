"""Utilities for disabling inherited proxy settings."""

from __future__ import annotations

from typing import Any


def disable_system_proxies() -> None:
    """Force requests sessions to ignore OS-level proxy settings.

    Monkey-patches :class:`requests.sessions.Session.__init__` so that every
    newly created session has ``trust_env=False`` and an empty proxies dict.
    The patch is applied at most once per process lifetime, guarded by a
    private class attribute ``_xmu_proxy_patched``.
    """
    import requests.sessions

    if getattr(requests.sessions.Session, "_xmu_proxy_patched", False):
        return

    original_init = requests.sessions.Session.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        """Session constructor wrapper that forces trust_env=False."""
        original_init(self, *args, **kwargs)
        self.trust_env = False
        self.proxies = {}

    requests.sessions.Session.__init__ = patched_init  # type: ignore[assignment]
    requests.sessions.Session._xmu_proxy_patched = True
