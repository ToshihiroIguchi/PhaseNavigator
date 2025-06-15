from typing import List
from pydantic import BaseModel, Field, validator

from ..core.config import settings


class DiagramRequest(BaseModel):
    """Request model for phase diagram generation."""
    
    formulas: List[str] = Field(
        ..., 
        alias="f",
        min_items=settings.min_formulas,
        max_items=settings.max_formulas,
        description="List of chemical formulas"
    )
    temperature: int = Field(
        default=settings.default_temperature,
        alias="temp",
        description="Temperature in Kelvin (0 or 300-2000)"
    )
    energy_cutoff: float = Field(
        default=settings.default_energy_cutoff,
        alias="e_cut",
        ge=0,
        le=settings.max_energy_cutoff,
        description="Energy cutoff in eV/atom"
    )
    functional: str = Field(
        default=settings.default_functional,
        description="DFT functional type"
    )
    
    @validator('temperature')
    def validate_temperature(cls, v):
        if v != 0 and not (settings.min_temperature <= v <= settings.max_temperature):
            raise ValueError(
                f"Temperature must be 0 K or between {settings.min_temperature}-{settings.max_temperature} K"
            )
        return v
    
    @validator('functional')
    def validate_functional(cls, v):
        if v not in settings.supported_functionals:
            raise ValueError(f"Unsupported functional: {v}. Supported: {settings.supported_functionals}")
        return v
    
    @validator('formulas')
    def validate_formulas(cls, v):
        # Remove empty strings and strip whitespace
        cleaned = [f.strip() for f in v if f.strip()]
        if len(cleaned) < settings.min_formulas:
            raise ValueError(f"At least {settings.min_formulas} chemical formulas are required")
        if len(cleaned) > settings.max_formulas:
            raise ValueError(f"Maximum {settings.max_formulas} formulas allowed")
        return cleaned


class FormDiagramRequest(BaseModel):
    """Request model for HTML form-based diagram generation."""
    
    formulas: str = Field(..., description="Comma-separated chemical formulas")
    temp: str = Field(default="0", description="Temperature as string")
    e_cut: float = Field(default=settings.default_energy_cutoff, description="Energy cutoff")
    functional: str = Field(default=settings.default_functional, description="DFT functional")
    
    def to_diagram_request(self) -> DiagramRequest:
        """Convert form request to API request format."""
        # Parse temperature
        try:
            temp_int = int(self.temp) if self.temp.strip() else 0
        except ValueError:
            temp_int = 0
        
        # Parse formulas
        formula_list = [f.strip() for f in self.formulas.split(",") if f.strip()]
        
        return DiagramRequest(
            f=formula_list,
            temp=temp_int,
            e_cut=self.e_cut,
            functional=self.functional
        )