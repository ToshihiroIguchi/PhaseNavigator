import pytest
from pydantic import ValidationError
from app.models.requests import DiagramRequest, FormDiagramRequest
from app.models.responses import PhaseInfo, DiagramMetadata


def test_diagram_request_validation():
    """Test DiagramRequest validation."""
    # Valid request
    request = DiagramRequest(
        f=["Fe2O3", "Al2O3"],
        temp=0,
        e_cut=0.2,
        functional="GGA_GGA_U_R2SCAN"
    )
    assert request.formulas == ["Fe2O3", "Al2O3"]
    assert request.temperature == 0
    
    # Invalid temperature
    with pytest.raises(ValidationError):
        DiagramRequest(
            f=["Fe2O3", "Al2O3"],
            temp=2500,  # Too high
            e_cut=0.2,
            functional="GGA_GGA_U_R2SCAN"
        )
    
    # Invalid functional
    with pytest.raises(ValidationError):
        DiagramRequest(
            f=["Fe2O3", "Al2O3"],
            temp=0,
            e_cut=0.2,
            functional="INVALID_FUNCTIONAL"
        )
    
    # Too few formulas
    with pytest.raises(ValidationError):
        DiagramRequest(
            f=["Fe2O3"],  # Only one formula
            temp=0,
            e_cut=0.2,
            functional="GGA_GGA_U_R2SCAN"
        )


def test_form_diagram_request_conversion():
    """Test FormDiagramRequest to DiagramRequest conversion."""
    form_request = FormDiagramRequest(
        formulas="Fe2O3, Al2O3, SiO2",
        temp="300",
        e_cut=0.3,
        functional="R2SCAN"
    )
    
    api_request = form_request.to_diagram_request()
    
    assert api_request.formulas == ["Fe2O3", "Al2O3", "SiO2"]
    assert api_request.temperature == 300
    assert api_request.energy_cutoff == 0.3
    assert api_request.functional == "R2SCAN"


def test_phase_info_model():
    """Test PhaseInfo model."""
    phase = PhaseInfo(
        formula="Fe2O3",
        composition="Fe2 O3",
        energy_per_atom=-5.123,
        total_energy=-25.615,
        formation_energy_per_atom=-1.234,
        correction=0.456,
        entry_id="mp-1234",
        temperature=300,
        num_atoms=5.0
    )
    
    assert phase.formula == "Fe2O3"
    assert phase.entry_id == "mp-1234"
    assert phase.temperature == 300


def test_diagram_metadata_model():
    """Test DiagramMetadata model."""
    metadata = DiagramMetadata(
        temperature=300,
        elements=["Fe", "O", "Al"],
        e_cut=0.2,
        functional="GGA_GGA_U_R2SCAN",
        num_phases=5
    )
    
    assert metadata.temperature == 300
    assert metadata.elements == ["Fe", "O", "Al"]
    assert metadata.num_phases == 5