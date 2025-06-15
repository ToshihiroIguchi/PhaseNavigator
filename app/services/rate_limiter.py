import time
from collections import defaultdict
from typing import Dict, List, Tuple

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter service for API requests."""
    
    def __init__(
        self,
        window_seconds: int = None,
        max_requests: int = None
    ):
        self.window_seconds = window_seconds or settings.rate_limit_window
        self.max_requests = max_requests or settings.rate_limit_max_requests
        self._request_log: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    
    def is_allowed(self, key: Tuple[str, str]) -> bool:
        """
        Check if a request is allowed based on rate limiting.
        
        Args:
            key: Tuple of (api_key_hash, client_ip)
            
        Returns:
            True if request is allowed, False if rate-limited
        """
        now = time.time()
        log = self._request_log[key]
        
        # Remove old entries outside the time window
        while log and now - log[0] > self.window_seconds:
            log.pop(0)
        
        # Check if we've exceeded the limit
        if len(log) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for key: {key[0][:8]}... from IP: {key[1]}")
            return False
        
        # Add current request timestamp
        log.append(now)
        logger.debug(f"Request allowed for key: {key[0][:8]}... ({len(log)}/{self.max_requests})")
        
        return True
    
    def get_remaining_requests(self, key: Tuple[str, str]) -> int:
        """
        Get the number of remaining requests for a key.
        
        Args:
            key: Tuple of (api_key_hash, client_ip)
            
        Returns:
            Number of remaining requests in current window
        """
        now = time.time()
        log = self._request_log[key]
        
        # Remove old entries
        while log and now - log[0] > self.window_seconds:
            log.pop(0)
        
        return max(0, self.max_requests - len(log))
    
    def get_reset_time(self, key: Tuple[str, str]) -> float:
        """
        Get the time when the rate limit will reset for a key.
        
        Args:
            key: Tuple of (api_key_hash, client_ip)
            
        Returns:
            Unix timestamp when rate limit resets
        """
        log = self._request_log[key]
        if not log:
            return time.time()
        
        return log[0] + self.window_seconds
    
    def clear_expired(self):
        """Clear expired entries from all logs."""
        now = time.time()
        expired_keys = []
        
        for key, log in self._request_log.items():
            # Remove old entries
            while log and now - log[0] > self.window_seconds:
                log.pop(0)
            
            # Mark empty logs for removal
            if not log:
                expired_keys.append(key)
        
        # Remove empty logs
        for key in expired_keys:
            del self._request_log[key]
        
        if expired_keys:
            logger.debug(f"Cleared {len(expired_keys)} expired rate limit entries")


# Global rate limiter instance
rate_limiter = RateLimiter()