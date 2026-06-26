import os
from typing import List
from pydantic import ConfigDict

try:
    from pydantic import BaseSettings
except ImportError:
    from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "PhaseNavigator"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Rate Limiting
    rate_limit_window: int = 30  # seconds
    rate_limit_max_requests: int = 10
    
    # Phase Diagram
    default_functional: str = "GGA_GGA_U_R2SCAN"
    supported_functionals: List[str] = ["GGA_GGA_U_R2SCAN", "R2SCAN", "GGA_GGA_U"]
    
    # Temperature constraints
    min_temperature: int = 300
    max_temperature: int = 2000
    default_temperature: int = 0
    
    # Energy constraints
    default_energy_cutoff: float = 0.2
    max_energy_cutoff: float = 2.0
    
    # Formula constraints
    min_formulas: int = 2
    max_formulas: int = 4
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "phasenav.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Security
    api_key_hash_length: int = 12
    MP_API_KEY: str | None = None
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()