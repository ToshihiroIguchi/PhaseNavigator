import time
from collections import defaultdict
from typing import Dict, List, Tuple

WINDOW = 30          # seconds
MAX_REQ = 10

# {key: [timestamps]}
_request_log: Dict[Tuple[str, str], List[float]] = defaultdict(list)


def check_limit(key: Tuple[str, str]) -> bool:
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