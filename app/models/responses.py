from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class PhaseInfo(BaseModel):
    """Information about a single phase in the diagram."""
    
    formula: str
    composition: str
    energy_per_atom: float
    total_energy: float
    formation_energy_per_atom: Optional[float]
    correction: float
    entry_id: str
    temperature: int
    num_atoms: float


class DiagramMetadata(BaseModel):
    """Metadata about the phase diagram calculation."""
    
    temperature: int
    elements: List[str]
    e_cut: float
    functional: str
    num_phases: int


class DiagramResponse(BaseModel):
    """Response model for phase diagram generation."""
    
    plot: Dict[str, Any]
    phase_info: List[PhaseInfo]
    metadata: DiagramMetadata


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    detail: str
    error_code: Optional[str] = None
    timestamp: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str
    app_name: str
    version: str
    timestamp: str