"""Bounded process-local login throttling for the single-worker portfolio demo."""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException

_attempts = OrderedDict()
_lock = Lock()


def check_login(username):
    key = username.casefold()
    current = monotonic()
    with _lock:
        if key not in _attempts:
            if len(_attempts) >= 10000:
                _attempts.popitem(last=False)
            _attempts[key] = deque()
        attempts = _attempts[key]
        while attempts and attempts[0] < current - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(
                429, "Too many login attempts; try again in one minute", headers={"Retry-After": "60"}
            )
        attempts.append(current)
        _attempts.move_to_end(key)
