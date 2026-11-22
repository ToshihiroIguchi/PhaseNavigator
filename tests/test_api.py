import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "PhaseNavigator"


def test_index_page():
    """Test main index page loads."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Phase Navigator" in response.content


def test_diagram_endpoint_no_api_key():
    """Test diagram endpoint without API key returns 400."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3", "Al2O3"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U_R2SCAN"
    })
    assert response.status_code == 400  # Missing required header


def test_diagram_endpoint_invalid_data():
    """Test diagram endpoint with invalid data."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3"],  # Only one formula (invalid)
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U_R2SCAN"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 400  # Validation error


def test_diagram_endpoint_invalid_functional():
    """Test diagram endpoint with invalid functional."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3", "Al2O3"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "INVALID_FUNCTIONAL"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 400  # Validation error

def test_validation_error_detail_is_human_readable():
    """Validation errors are returned as plain sentences, not pydantic internals."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "At least 2 chemical formulas" in detail
    assert "'type'" not in detail
    assert "'loc'" not in detail


def test_validation_error_for_space_separated_formulas():
    """A formula containing a space is reported with a clear message."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3 Al2O3", "SiO2"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 400
    assert "contains a space" in response.json()["detail"]


def test_validation_error_for_missing_api_key_header():
    """A missing header is reported by name."""
    response = client.post("/api/diagrams/", json={"f": ["Fe2O3", "Al2O3"]})
    assert response.status_code == 400
    assert "X-API-KEY" in response.json()["detail"] or "x_api_key" in response.json()["detail"]
