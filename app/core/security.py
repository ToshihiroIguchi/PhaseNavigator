import hashlib
from typing import Tuple

from .config import settings


def hash_api_key(api_key: str) -> str:
    """
    Generate a short SHA-256 hash of the API key for logging and rate limiting.
    
    Args:
        api_key: The Materials Project API key
        
    Returns:
        Short hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()[:settings.api_key_hash_length]


def create_rate_limit_key(api_key_hash: str, client_ip: str) -> Tuple[str, str]:
    """
    Create a rate limiting key from API key hash and client IP.
    
    Args:
        api_key_hash: Hashed API key
        client_ip: Client IP address
        
    Returns:
        Tuple of (api_key_hash, client_ip) for rate limiting
    """
    return (api_key_hash, client_ip)


def validate_api_key(api_key: str) -> bool:
    """
    Basic validation for Materials Project API key format.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if the key appears to be in correct format
    """
    if not api_key or not isinstance(api_key, str):
        return False
    
    # Materials Project API keys are typically 32 characters long
    if len(api_key) < 20:
        return False
        
    return True