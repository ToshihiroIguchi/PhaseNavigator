import json
from typing import List, Dict, Any
from pymatgen.analysis.phase_diagram import CompoundPhaseDiagram, PDPlotter
from pymatgen.core.composition import Composition
from pymatgen.entries.computed_entries import ComputedEntry

from ..core.logging import get_logger
from ..models.responses import PhaseInfo, DiagramMetadata, DiagramResponse
from .materials_client import MaterialsProjectClient

logger = get_logger(__name__)


def build_dummy_label_map(phase_diagram: CompoundPhaseDiagram) -> Dict[str, str]:
    """
    Map the dummy species symbols used internally by CompoundPhaseDiagram
    (e.g. "Xf0+") to the terminal formulas the user entered (e.g. "Fe2O3").

    Args:
        phase_diagram: The compound phase diagram built from the terminals.

    Returns:
        Dictionary from dummy symbol to terminal reduced formula.
    """
    label_map: Dict[str, str] = {}
    for terminal in phase_diagram.terminal_compositions:
        for normalized, dummy in phase_diagram.species_mapping.items():
            if terminal.fractional_composition.almost_equals(normalized):
                label_map[str(dummy)] = terminal.reduced_formula
                break
    return label_map


def replace_dummy_labels(data: Any, label_map: Dict[str, str]) -> Any:
    """
    Recursively replace dummy species symbols in every string of a JSON-like
    structure (such as a Plotly figure dict).

    Args:
        data: Nested dicts, lists and strings.
        label_map: Mapping from dummy symbol to the text to show instead.

    Returns:
        A new structure with the replacements applied; non-strings are kept.
    """
    if isinstance(data, str):
        # Replace longer symbols first so one symbol cannot clobber another.
        for symbol in sorted(label_map, key=len, reverse=True):
            data = data.replace(symbol, label_map[symbol])
        return data
    if isinstance(data, list):
        return [replace_dummy_labels(item, label_map) for item in data]
    if isinstance(data, dict):
        return {key: replace_dummy_labels(value, label_map) for key, value in data.items()}
    return data


class PhaseAnalyzer:
    """Service for analyzing phase diagrams and extracting phase information."""
    
    def __init__(self, materials_client: MaterialsProjectClient):
        self.materials_client = materials_client
    
    def extract_phase_info(
        self,
        phase_diagram: CompoundPhaseDiagram,
        original_entries: List[ComputedEntry],
        temperature: int
    ) -> List[PhaseInfo]:
        """Extract phase information from phase diagram and entries."""
        phase_info = []
        stable_entries = phase_diagram.stable_entries
        
        logger.info(f"Extracting phase info for {len(stable_entries)} stable phases")
        
        for stable_entry in stable_entries:
            # Get original entry for better data access
            orig_entry = self._get_original_entry(stable_entry, original_entries)
            
            # Extract phase data
            phase_data = self._extract_phase_data(
                stable_entry=stable_entry,
                orig_entry=orig_entry,
                phase_diagram=phase_diagram,
                temperature=temperature
            )
            
            phase_info.append(phase_data)
        
        # Sort by formation energy (most stable first)
        phase_info.sort(
            key=lambda x: x.formation_energy_per_atom if x.formation_energy_per_atom is not None else float('inf')
        )
        
        return phase_info
    
    def _get_original_entry(
        self,
        stable_entry: ComputedEntry,
        original_entries: List[ComputedEntry]
    ) -> ComputedEntry:
        """Get the original entry corresponding to a stable entry."""
        # Check if entry has original_entry attribute
        if hasattr(stable_entry, 'original_entry') and stable_entry.original_entry:
            return stable_entry.original_entry
        
        # Fallback: try to match with original entries by energy
        for orig in original_entries:
            if abs(orig.energy - stable_entry.energy) < 1e-4:
                return orig
        
        # Use stable entry as fallback
        logger.warning(f"No original entry found for {stable_entry.composition}")
        return stable_entry
    
    def _extract_phase_data(
        self,
        stable_entry: ComputedEntry,
        orig_entry: ComputedEntry,
        phase_diagram: CompoundPhaseDiagram,
        temperature: int
    ) -> PhaseInfo:
        """Extract data for a single phase."""
        composition = orig_entry.composition
        formula = composition.reduced_formula
        
        # Energy information
        energy_per_atom = stable_entry.energy_per_atom
        total_energy = stable_entry.energy
        
        # Formation energy calculation
        try:
            formation_energy_per_atom = phase_diagram.get_form_energy_per_atom(stable_entry)
        except Exception as e:
            logger.warning(f"Could not calculate formation energy for {formula}: {e}")
            formation_energy_per_atom = None
        
        # Get MP ID
        entry_id = self._extract_mp_id(orig_entry)
        
        # Energy correction
        correction = getattr(stable_entry, 'correction', getattr(orig_entry, 'correction', 0))
        
        logger.debug(f"Phase: {formula}, MP ID: {entry_id}")
        
        return PhaseInfo(
            formula=formula,
            composition=str(composition),
            energy_per_atom=round(energy_per_atom, 4),
            total_energy=round(total_energy, 4),
            formation_energy_per_atom=round(formation_energy_per_atom, 4) if formation_energy_per_atom is not None else None,
            correction=round(correction, 4),
            entry_id=entry_id,
            temperature=temperature,
            num_atoms=composition.num_atoms
        )
    
    def _extract_mp_id(self, entry: ComputedEntry) -> str:
        """Extract Materials Project ID from entry."""
        # Check different possible attributes for MP ID
        for attr_name in ['entry_id', 'material_id', 'mp_id']:
            if hasattr(entry, attr_name):
                value = getattr(entry, attr_name)
                if value and str(value) != 'None':
                    return str(value)
        
        # Check data dictionary if available
        if hasattr(entry, 'data') and isinstance(entry.data, dict):
            for key in ['material_id', 'entry_id', 'mp_id', 'task_id']:
                if key in entry.data and entry.data[key]:
                    return str(entry.data[key])
        
        return 'Unknown'
    
    @staticmethod
    def _check_terminals_present(
        formulas: List[str],
        terminals: List[Composition],
        entries: List[ComputedEntry]
    ) -> None:
        """
        Make sure every terminal formula still has an entry of its own composition.

        Args:
            formulas: Formulas as entered by the user.
            terminals: The same formulas as compositions.
            entries: Entries that remain after license filtering.

        Raises:
            ValueError: If a terminal has no entry (non-commercial entries were removed).
        """
        for formula, terminal in zip(formulas, terminals):
            if not any(
                entry.composition.reduced_composition.almost_equals(terminal.reduced_composition)
                for entry in entries
            ):
                raise ValueError(
                    f"No CC BY 4.0 entry found for '{formula}'. "
                    "Enable non-commercial data to include GNoME entries."
                )

    def generate_phase_diagram(
        self,
        formulas: List[str],
        temperature: int,
        energy_cutoff: float,
        functional: str,
        api_key: str,
        include_non_commercial: bool = False
    ) -> DiagramResponse:
        """
        Generate phase diagram and extract phase information.
        
        Args:
            formulas: List of chemical formulas
            temperature: Temperature in Kelvin
            energy_cutoff: Energy cutoff for unstable phases
            functional: DFT functional type
            api_key: Materials Project API key
            include_non_commercial: Keep non-commercial (CC BY-NC, e.g. GNoME) entries
            
        Returns:
            Complete diagram response with plot and phase info

        Raises:
            ValueError: On invalid input, API errors, or when excluding
                non-commercial data leaves a terminal formula without any entry.
        """
        logger.info(f"Generating phase diagram for {formulas} at {temperature}K")
        
        # Get elements from formulas
        elements = self.materials_client.get_elements_from_formulas(formulas)
        
        # Fetch entries from Materials Project
        entries, excluded = self.materials_client.fetch_entries(
            elements, temperature, functional, include_non_commercial
        )
        
        # Build phase diagram
        terminals = [Composition(f) for f in formulas]
        if excluded:
            self._check_terminals_present(formulas, terminals, entries)
        phase_diagram = CompoundPhaseDiagram(
            entries,
            terminals,
            normalize_terminal_compositions=True
        )
        
        # Generate plot
        plotter = PDPlotter(phase_diagram, backend="plotly", show_unstable=energy_cutoff)
        fig = plotter.get_plot()
        plot_data = replace_dummy_labels(
            json.loads(fig.to_json()),
            build_dummy_label_map(phase_diagram)
        )
        
        # Extract phase information
        phase_info = self.extract_phase_info(phase_diagram, entries, temperature)
        
        # Create metadata
        metadata = DiagramMetadata(
            temperature=temperature,
            elements=elements,
            e_cut=energy_cutoff,
            functional=functional,
            num_phases=len(phase_info),
            excluded_non_commercial=excluded,
            include_non_commercial=include_non_commercial
        )
        
        logger.info(f"Phase diagram generated successfully with {len(phase_info)} phases")
        
        return DiagramResponse(
            plot=plot_data,
            phase_info=phase_info,
            metadata=metadata
        )