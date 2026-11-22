import re
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

def _build_offline_entries():
    """Create a small Fe-Al-O set of computed entries without network access."""
    from pymatgen.core import Composition
    from pymatgen.entries.computed_entries import ComputedEntry

    data = [
        ("Fe", -8.3), ("Al", -3.7), ("O", -4.9),
        ("Fe2O3", -38.0), ("Al2O3", -37.5), ("FeAl2O4", -50.0),
    ]
    return [
        ComputedEntry(Composition(formula), energy, entry_id=f"mp-{i}")
        for i, (formula, energy) in enumerate(data)
    ]


def test_generated_plot_uses_formulas_not_dummy_species():
    """Axis labels show the entered formulas instead of dummy symbols like Xg0+."""
    import json
    from app.services.phase_analyzer import PhaseAnalyzer

    client = Mock()
    client.get_elements_from_formulas.return_value = ["Al", "Fe", "O"]
    client.fetch_entries.return_value = _build_offline_entries()

    result = PhaseAnalyzer(client).generate_phase_diagram(
        formulas=["Fe2O3", "Al2O3"],
        temperature=0,
        energy_cutoff=0.2,
        functional="GGA_GGA_U",
        api_key="unused",
    )

    plot_json = json.dumps(result.plot)
    assert "Al2O3" in plot_json
    assert not re.search(r"\bX[a-z]\d?\+", plot_json)


def test_replace_dummy_labels_is_recursive():
    """Replacement reaches nested strings and keeps non-string values."""
    from app.services.phase_analyzer import replace_dummy_labels

    data = {"a": ["Fraction Xg0+", 1, None], "b": {"c": "Xf0+ and Xg0+"}}
    result = replace_dummy_labels(data, {"Xf0+": "Fe2O3", "Xg0+": "Al2O3"})
    assert result == {
        "a": ["Fraction Al2O3", 1, None],
        "b": {"c": "Fe2O3 and Al2O3"},
    }
