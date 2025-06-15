import pytest
from unittest.mock import Mock, patch
from app.services.materials_client import MaterialsProjectClient
from app.services.rate_limiter import RateLimiter
from app.core.security import hash_api_key, validate_api_key


def test_hash_api_key():
    """Test API key hashing."""
    api_key = "test_api_key_32_characters_long!"
    hashed = hash_api_key(api_key)
    assert len(hashed) == 12
    assert isinstance(hashed, str)
    
    # Same key should produce same hash
    hashed2 = hash_api_key(api_key)
    assert hashed == hashed2


def test_validate_api_key():
    """Test API key validation."""
    # Valid key
    valid_key = "abcdefghijklmnopqrstuvwxyz123456"
    assert validate_api_key(valid_key) == True
    
    # Invalid keys
    assert validate_api_key("") == False
    assert validate_api_key("short") == False
    assert validate_api_key("toolongandcontainsinvalidcharacters!") == False
    assert validate_api_key(None) == False


def test_materials_client_elements_extraction():
    """Test element extraction from formulas."""
    client = MaterialsProjectClient("dummy_key")
    
    formulas = ["Fe2O3", "Al2O3", "SiO2"]
    elements = client.get_elements_from_formulas(formulas)
    
    assert set(elements) == {"Fe", "O", "Al", "Si"}
    assert elements == sorted(elements)  # Should be sorted


def test_materials_client_functional_mapping():
    """Test functional mapping."""
    client = MaterialsProjectClient("dummy_key")
    
    # Valid functionals
    assert client.get_functional_mapping("GGA_GGA_U_R2SCAN") == ["GGA_GGA+U", "R2SCAN"]
    assert client.get_functional_mapping("R2SCAN") == ["R2SCAN"]
    assert client.get_functional_mapping("GGA_GGA_U") == ["GGA_GGA+U"]
    
    # Invalid functional
    with pytest.raises(ValueError):
        client.get_functional_mapping("INVALID")


def test_rate_limiter():
    """Test rate limiter functionality."""
    limiter = RateLimiter(window_seconds=10, max_requests=3)
    
    key = ("test_hash", "127.0.0.1")
    
    # Should allow first 3 requests
    assert limiter.is_allowed(key) == True
    assert limiter.is_allowed(key) == True
    assert limiter.is_allowed(key) == True
    
    # Should block 4th request
    assert limiter.is_allowed(key) == False
    
    # Check remaining requests
    assert limiter.get_remaining_requests(key) == 0