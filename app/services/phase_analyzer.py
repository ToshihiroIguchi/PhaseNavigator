import json
from typing import List, Dict, Any
from pymatgen.analysis.phase_diagram import CompoundPhaseDiagram, PDPlotter
from pymatgen.core.composition import Composition
from pymatgen.entries.computed_entries import ComputedEntry

from ..core.logging import get_logger
from ..models.responses import PhaseInfo, DiagramMetadata, DiagramResponse
from .materials_client import MaterialsProjectClient

logger = get_logger(__name__)


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
    
    def generate_phase_diagram(
        self,
        formulas: List[str],
        temperature: int,
        energy_cutoff: float,
        functional: str,
        api_key: str
    ) -> DiagramResponse:
        """
        Generate phase diagram and extract phase information.
        
        Args:
            formulas: List of chemical formulas
            temperature: Temperature in Kelvin
            energy_cutoff: Energy cutoff for unstable phases
            functional: DFT functional type
            api_key: Materials Project API key
            
        Returns:
            Complete diagram response with plot and phase info
        """
        logger.info(f"Generating phase diagram for {formulas} at {temperature}K")
        
        # Get elements from formulas
        elements = self.materials_client.get_elements_from_formulas(formulas)
        
        # Fetch entries from Materials Project
        entries = self.materials_client.fetch_entries(elements, temperature, functional)
        
        # Build phase diagram
        terminals = [Composition(f) for f in formulas]
        phase_diagram = CompoundPhaseDiagram(
            entries,
            terminals,
            normalize_terminal_compositions=True
        )
        
        # Generate plot
        plotter = PDPlotter(phase_diagram, backend="plotly", show_unstable=energy_cutoff)
        fig = plotter.get_plot()
        plot_data = json.loads(fig.to_json())
        
        # Extract phase information
        phase_info = self.extract_phase_info(phase_diagram, entries, temperature)
        
        # Create metadata
        metadata = DiagramMetadata(
            temperature=temperature,
            elements=elements,
            e_cut=energy_cutoff,
            functional=functional,
            num_phases=len(phase_info)
        )
        
        logger.info(f"Phase diagram generated successfully with {len(phase_info)} phases")
        
        return DiagramResponse(
            plot=plot_data,
            phase_info=phase_info,
            metadata=metadata
        )