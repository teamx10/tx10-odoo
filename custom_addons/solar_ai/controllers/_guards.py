import time
from collections import defaultdict
from threading import Lock

from odoo.exceptions import AccessError

RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_MAX_CALLS = 20

_rate_limit_lock = Lock()
_rate_limit_state: dict[int, list[float]] = defaultdict(list)


def check_authorized(env):
    """Only project-manager (or admin) can spend org LLM budget."""
    if env.user._is_admin():
        return
    if not env.user.has_group("project.group_project_manager"):
        err = "Solar AI: this endpoint requires the Project Manager group."
        raise AccessError(err)


def check_rate_limit(user_id) -> bool:
    """Sliding-window rate limit per user.

    NOTE: per-worker in-memory state — not shared across gunicorn workers.
    With N workers the effective limit is 20*N calls / 60 s, making this
    guard weaker in multi-worker production deployments.
    A future fix would use Redis or PostgreSQL for shared state.
    Tracked in: TODO — replace with shared-state rate limiter before scaling beyond 2 workers.
    """
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    with _rate_limit_lock:
        calls = _rate_limit_state[user_id]
        calls[:] = [t for t in calls if t > cutoff]
        if not calls:
            _rate_limit_state.pop(user_id, None)
            _rate_limit_state[user_id].append(now)
            return True
        if len(calls) >= RATE_LIMIT_MAX_CALLS:
            return False
        calls.append(now)
    return True


# Backward-compat aliases (tests import the underscore names)
_check_authorized = check_authorized
_check_rate_limit = check_rate_limit
