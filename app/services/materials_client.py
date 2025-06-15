from typing import List
from mp_api.client import MPRester
from pymatgen.core.composition import Composition
from pymatgen.entries.computed_entries import ComputedEntry

from ..core.logging import get_logger
from ..core.config import settings

logger = get_logger(__name__)


class MaterialsProjectClient:
    """Client for Materials Project API interactions."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
    
    def get_client(self) -> MPRester:
        """Get or create MP client instance."""
        if self._client is None:
            self._client = MPRester(api_key=self.api_key)
        return self._client
    
    def get_elements_from_formulas(self, formulas: List[str]) -> List[str]:
        """Extract unique element symbols from chemical formulas."""
        elements = set()
        for formula in formulas:
            try:
                composition = Composition(formula)
                elements.update(el.symbol for el in composition)
            except Exception as e:
                logger.error(f"Error parsing formula {formula}: {e}")
                raise ValueError(f"Invalid chemical formula: {formula}")
        
        return sorted(elements)
    
    def get_functional_mapping(self, functional: str) -> List[str]:
        """Map functional name to Materials Project thermo types."""
        functional_map = {
            "GGA_GGA_U_R2SCAN": ["GGA_GGA+U", "R2SCAN"],
            "R2SCAN": ["R2SCAN"],
            "GGA_GGA_U": ["GGA_GGA+U"]
        }
        
        if functional not in functional_map:
            raise ValueError(f"Unsupported functional: {functional}")
        
        return functional_map[functional]
    
    def fetch_entries(
        self,
        elements: List[str],
        temperature: int,
        functional: str
    ) -> List[ComputedEntry]:
        """
        Fetch computed entries from Materials Project.
        
        Args:
            elements: List of element symbols
            temperature: Temperature in Kelvin (0 for 0K, >0 for Gibbs)
            functional: DFT functional type
            
        Returns:
            List of computed entries
        """
        thermo_types = self.get_functional_mapping(functional)
        additional_criteria = {"thermo_types": thermo_types}
        
        logger.info(f"Fetching entries for elements: {elements}, T={temperature}K, functional={functional}")
        
        try:
            with self.get_client() as client:
                if temperature == 0:
                    entries = client.get_entries_in_chemsys(
                        elements,
                        additional_criteria=additional_criteria
                    )
                else:
                    entries = client.get_entries_in_chemsys(
                        elements,
                        use_gibbs=temperature,
                        additional_criteria=additional_criteria
                    )
            
            logger.info(f"Retrieved {len(entries)} entries from Materials Project")
            
            if not entries:
                raise ValueError(
                    f"No materials found for elements {elements} in Materials Project database"
                )
            
            return entries
            
        except Exception as e:
            logger.error(f"Error fetching entries: {e}")
            if "Invalid authentication credentials" in str(e):
                raise ValueError("Invalid Materials Project API key")
            elif "REST query returned with error status code 401" in str(e):
                raise ValueError("Invalid Materials Project API key")
            else:
                raise ValueError(f"Materials Project API error: {str(e)}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client is not None:
            # MP client handles its own cleanup
            pass