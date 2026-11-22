import itertools
import re
from typing import List, Set, Tuple

from mp_api.client import MPRester
from pymatgen.entries.computed_entries import ComputedEntry

from ..core.logging import get_logger
from ..core.config import settings
from .formula_parser import parse_formula

logger = get_logger(__name__)

# Functional suffix appended to Materials Project entry IDs (e.g. "mp-1143-r2SCAN").
_ENTRY_SUFFIX_PATTERN = re.compile(r"-(?:r2SCAN|GGA\+U|GGA|scan|pbe|hsesol)$", re.IGNORECASE)

# Materials Project license label for non-commercial data (e.g. GNoME).
NON_COMMERCIAL_LICENSE = "BY-NC"


def base_material_id(entry_id: object) -> str:
    """
    Strip the functional suffix from an entry ID.

    Args:
        entry_id: Entry ID such as "mp-1143-r2SCAN" or "mp-31770-GGA+U".

    Returns:
        The bare material ID (e.g. "mp-1143"); unchanged if there is no suffix.
    """
    return _ENTRY_SUFFIX_PATTERN.sub("", str(entry_id))


def subsystem_chemsys(elements: List[str]) -> List[str]:
    """
    List every chemical subsystem of the given elements.

    Args:
        elements: Element symbols, e.g. ["Al", "Fe", "O"].

    Returns:
        Hyphen-joined chemsys strings from single elements up to the full system.
    """
    ordered = sorted(elements)
    return [
        "-".join(combo)
        for size in range(1, len(ordered) + 1)
        for combo in itertools.combinations(ordered, size)
    ]


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
            composition = parse_formula(formula)
            elements.update(el.symbol for el in composition)

        return sorted(elements)
    
    def get_functional_mapping(self, functional: str) -> List[str]:
        """
        Map functional name to Materials Project thermo types.

        The mixed option uses the single joint thermo type, so each material appears
        once and all energies share one corrected scale. Requesting the GGA/GGA+U and
        R2SCAN types separately would return the same material twice on different
        energy scales.
        """
        functional_map = {
            "GGA_GGA_U_R2SCAN": ["GGA_GGA+U_R2SCAN"],
            "R2SCAN": ["R2SCAN"],
            "GGA_GGA_U": ["GGA_GGA+U"]
        }
        
        if functional not in functional_map:
            raise ValueError(f"Unsupported functional: {functional}")
        
        return functional_map[functional]
    
    def fetch_non_commercial_ids(self, client: MPRester, elements: List[str]) -> Set[str]:
        """
        Look up materials that carry non-commercial terms (e.g. GNoME).

        Args:
            client: An open Materials Project client.
            elements: Element symbols of the chemical system.

        Returns:
            Bare material IDs whose license is CC BY-NC or whose batch is GNoME.

        Raises:
            ValueError: If the license information cannot be retrieved.
        """
        try:
            docs = client.materials.search(
                chemsys=subsystem_chemsys(elements),
                fields=["material_id", "builder_meta"],
            )
        except Exception as e:
            logger.error(f"License lookup failed: {e}")
            raise ValueError(
                "Could not verify data licenses with the Materials Project. "
                "Try again, or enable non-commercial data to skip this check."
            )

        ids: Set[str] = set()
        for doc in docs:
            meta = getattr(doc, "builder_meta", None)
            license_name = getattr(meta, "license", None)
            batch_id = str(getattr(meta, "batch_id", "") or "")
            if license_name == NON_COMMERCIAL_LICENSE or batch_id.lower().startswith("gnome"):
                ids.add(str(doc.material_id))
        return ids

    def fetch_entries(
        self,
        elements: List[str],
        temperature: int,
        functional: str,
        include_non_commercial: bool = False
    ) -> Tuple[List[ComputedEntry], int]:
        """
        Fetch computed entries from Materials Project.
        
        Args:
            elements: List of element symbols
            temperature: Temperature in Kelvin (0 for 0K, >0 for Gibbs)
            functional: DFT functional type
            include_non_commercial: Keep entries with non-commercial (CC BY-NC) terms
            
        Returns:
            Tuple of (computed entries, number of non-commercial entries excluded)

        Raises:
            ValueError: If no entries are found, the API key is invalid, or the
                license check fails while non-commercial data is excluded.
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
            
                excluded = 0
                if not include_non_commercial:
                    blocked = self.fetch_non_commercial_ids(client, elements)
                    kept = [e for e in entries if base_material_id(e.entry_id) not in blocked]
                    excluded = len(entries) - len(kept)
                    entries = kept

            logger.info(
                f"Retrieved {len(entries)} entries from Materials Project "
                f"({excluded} non-commercial entries excluded)"
            )
            
            if not entries:
                raise ValueError(
                    f"No materials found for elements {elements} in Materials Project database"
                )
            
            return entries, excluded
            
        except ValueError:
            # Already a user-facing message (no entries, license check failed).
            raise
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