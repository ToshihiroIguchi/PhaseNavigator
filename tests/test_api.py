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


def test_plotly_js_is_served_locally():
    """The plotly.js bundle is served by the app, not by a third-party CDN."""
    response = client.get("/vendor/plotly.min.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert len(response.content) > 100_000

    page = client.get("/")
    assert b"/vendor/plotly.min.js" in page.content
    assert b"cdn.plot.ly" not in page.content


def _fake_diagram_response():
    from app.models.responses import DiagramMetadata, DiagramResponse

    return DiagramResponse(
        plot={"data": [], "layout": {}},
        phase_info=[],
        metadata=DiagramMetadata(
            temperature=0, elements=["Fe", "O"], e_cut=0.2,
            functional="GGA_GGA_U", num_phases=0,
        ),
    )


@pytest.mark.parametrize("payload_extra, expected", [({}, False), ({"include_non_commercial": True}, True)])
def test_diagram_endpoint_passes_non_commercial_flag(payload_extra, expected):
    """The flag defaults to False and is forwarded to the analyzer when allowed at startup."""
    payload = {"f": ["Fe2O3", "Al2O3"], **payload_extra}
    with patch("app.api.diagrams.settings.allow_non_commercial", True),             patch("app.api.diagrams.PhaseAnalyzer") as analyzer_cls:
        analyzer_cls.return_value.generate_phase_diagram.return_value = _fake_diagram_response()
        response = client.post(
            "/api/diagrams/", json=payload,
            headers={"X-API-KEY": "abcdefghijklmnopqrstuvwxyz123456"},
        )

    assert response.status_code == 200
    kwargs = analyzer_cls.return_value.generate_phase_diagram.call_args.kwargs
    assert kwargs["include_non_commercial"] is expected


def test_diagram_endpoint_rejects_non_commercial_when_disabled():
    """Without the startup option, requesting non-commercial data is refused."""
    payload = {"f": ["Fe2O3", "Al2O3"], "include_non_commercial": True}
    with patch("app.api.diagrams.settings.allow_non_commercial", False),             patch("app.api.diagrams.PhaseAnalyzer") as analyzer_cls:
        response = client.post(
            "/api/diagrams/", json=payload,
            headers={"X-API-KEY": "abcdefghijklmnopqrstuvwxyz123456"},
        )

    assert response.status_code == 403
    analyzer_cls.return_value.generate_phase_diagram.assert_not_called()


def test_index_page_hides_non_commercial_toggle_by_default():
    """The option is absent from the page unless enabled at startup."""
    with patch("app.main.settings.allow_non_commercial", False):
        html = client.get("/").text
    assert 'id="include-non-commercial"' not in html


def test_index_page_has_non_commercial_toggle_off_by_default():
    """When enabled at startup the opt-in switch is present and not pre-checked."""
    with patch("app.main.settings.allow_non_commercial", True):
        html = client.get("/").text
    assert 'id="include-non-commercial"' in html
    assert "checked" not in html.split('id="include-non-commercial"')[1].split(">")[0]
