import time
from collections import defaultdict

WINDOW = 30          # seconds
MAX_REQ = 10

# {key: [timestamps]}
_request_log: defaultdict[tuple, list] = defaultdict(list)


def check_limit(key: tuple[str, str]) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    log = _request_log[key]
    # drop old entries
    while log and now - log[0] > WINDOW:
        log.pop(0)
    if len(log) >= MAX_REQ:
        return False
    log.append(now)
    return True
