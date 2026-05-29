"""Shared ANSI color constants and helper utilities for terminal output."""

import re

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')


class Colors:
    """ANSI escape code constants for colorful terminal output."""

    __slots__ = ()
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'
    BG_BLUE = '\033[44m'
    BG_GREEN = '\033[42m'
    BG_CYAN = '\033[46m'


def colored(text: str, *attrs: str) -> str:
    """Wrap *text* with one or more ANSI attributes.

    Usage::

        colored("hello", Colors.OKGREEN, Colors.BOLD)
        # → green bold "hello" + reset

    Args:
        text: The string to decorate.
        *attrs: One or more ANSI escape codes (e.g. ``Colors.FAIL``).

    Returns:
        The decorated string with a trailing reset code.
    """
    prefix = ''.join(attrs)
    return f"{prefix}{text}{Colors.ENDC}" if prefix else text


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from *text*.

    Useful when you need plain-text length or want to log without
    garbled escape codes.

    Args:
        text: A string that may contain ANSI escapes.

    Returns:
        The cleaned string with no ANSI sequences.
    """
    return _ANSI_RE.sub('', text)
