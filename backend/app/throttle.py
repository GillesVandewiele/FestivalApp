"""A guess limiter for device codes.

Codes are 12 characters so a volunteer can type them. Sixty bits is comfortable
against offline attack but the whole point of a bearer token is that it is tried
online, so the online rate is the control that matters. Twenty failures per address
per five minutes puts a full search of the space out of reach by a wide margin.

In-process state, which matches the deployment: one free Render instance. If the
backend is ever scaled out, this needs to move to shared storage, and the code
length should be revisited at the same time.
"""

import time

MAX_FAILURES = 20
WINDOW_SECONDS = 300

_failures: dict[str, list[float]] = {}


def _prune(now: float, attempts: list[float]) -> list[float]:
    return [t for t in attempts if now - t < WINDOW_SECONDS]


def is_blocked(ip: str) -> bool:
    attempts = _prune(time.monotonic(), _failures.get(ip, []))
    _failures[ip] = attempts
    return len(attempts) >= MAX_FAILURES


def record_failure(ip: str) -> None:
    now = time.monotonic()
    _failures[ip] = _prune(now, _failures.get(ip, [])) + [now]


def clear(ip: str) -> None:
    """A correct code proves the caller is not guessing."""
    _failures.pop(ip, None)


def reset() -> None:
    """Tests only."""
    _failures.clear()
