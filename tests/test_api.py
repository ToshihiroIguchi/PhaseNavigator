import pytest
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
    """Test diagram endpoint without API key returns 422."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3", "Al2O3"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U_R2SCAN"
    })
    assert response.status_code == 422  # Missing required header


def test_diagram_endpoint_invalid_data():
    """Test diagram endpoint with invalid data."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3"],  # Only one formula (invalid)
        "temp": 0,
        "e_cut": 0.2,
        "functional": "GGA_GGA_U_R2SCAN"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 422  # Validation error


def test_diagram_endpoint_invalid_functional():
    """Test diagram endpoint with invalid functional."""
    response = client.post("/api/diagrams/", json={
        "f": ["Fe2O3", "Al2O3"],
        "temp": 0,
        "e_cut": 0.2,
        "functional": "INVALID_FUNCTIONAL"
    }, headers={"X-API-KEY": "test_key_32_characters_long_123"})
    assert response.status_code == 422  # Validation error