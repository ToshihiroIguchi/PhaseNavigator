import hashlib, json, logging
from typing import List

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from mp_api.client import MPRester
from pymatgen.analysis.phase_diagram import CompoundPhaseDiagram, PDPlotter
from pymatgen.core.composition import Composition
from pymatgen.entries.computed_entries import ComputedEntry

# ─────────── logging ───────────
logger = logging.getLogger("phasenav")
fh = logging.FileHandler("phasenav.log")
fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
logger.addHandler(fh)
logger.setLevel(logging.INFO)
# ───────────────────────────────

def _elements(flist: List[str]) -> List[str]:
    """Return sorted unique element symbols in formulas."""
    return sorted({el.symbol for f in flist for el in Composition(f)})

def _hash_key(key: str) -> str:
    """Short SHA‐256 digest of API key."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]

def _extract_phase_info(pd: CompoundPhaseDiagram, original_entries: List[ComputedEntry], temp: int) -> List[dict]:
    """Extract phase information from phase diagram and entries."""
    phase_info = []
    
    # Get all stable phases from the phase diagram
    stable_entries = pd.stable_entries
    
    for stable_entry in stable_entries:
        # Check if entry has original_entry attribute (common in CompoundPhaseDiagram)
        if hasattr(stable_entry, 'original_entry') and stable_entry.original_entry:
            orig_entry = stable_entry.original_entry
            logger.info(f"Using original_entry: {orig_entry.composition.reduced_formula}")
        else:
            # Fallback: try to match with original entries by energy and composition
            orig_entry = None
            for orig in original_entries:
                if (abs(orig.energy - stable_entry.energy) < 1e-4):  # More tolerant matching
                    orig_entry = orig
                    break
            
            if orig_entry is None:
                # Use stable entry as fallback
                orig_entry = stable_entry
                logger.warning(f"No original entry found for {stable_entry.composition}")
        
        # Get composition and formula from original entry
        composition = orig_entry.composition
        formula = composition.reduced_formula
        
        # Energy information from stable entry (this is what's used in the diagram)
        energy_per_atom = stable_entry.energy_per_atom
        total_energy = stable_entry.energy
        
        # Formation energy calculation (relative to elements)
        try:
            formation_energy_per_atom = pd.get_form_energy_per_atom(stable_entry)
        except:
            formation_energy_per_atom = None
            
        # Try to get MP ID from original entry
        entry_id = 'Unknown'
        
        # Check different possible attributes for MP ID
        for attr_name in ['entry_id', 'material_id', 'mp_id']:
            if hasattr(orig_entry, attr_name):
                value = getattr(orig_entry, attr_name)
                if value and str(value) != 'None':
                    entry_id = str(value)
                    break
        
        # Check data dictionary if available
        if entry_id == 'Unknown' and hasattr(orig_entry, 'data') and isinstance(orig_entry.data, dict):
            for key in ['material_id', 'entry_id', 'mp_id', 'task_id']:
                if key in orig_entry.data and orig_entry.data[key]:
                    entry_id = str(orig_entry.data[key])
                    break
        
        # Energy correction
        correction = getattr(stable_entry, 'correction', getattr(orig_entry, 'correction', 0))
        
        logger.info(f"Phase: {formula} (was: {stable_entry.composition.reduced_formula}), MP ID: {entry_id}")
        
        phase_data = {
            'formula': formula,
            'composition': str(composition),
            'energy_per_atom': round(energy_per_atom, 4),
            'total_energy': round(total_energy, 4),
            'formation_energy_per_atom': round(formation_energy_per_atom, 4) if formation_energy_per_atom is not None else None,
            'correction': round(correction, 4),
            'entry_id': entry_id,
            'temperature': temp,
            'num_atoms': composition.num_atoms
        }
        
        phase_info.append(phase_data)
    
    # Sort by formation energy (most stable first)
    phase_info.sort(key=lambda x: x['formation_energy_per_atom'] if x['formation_energy_per_atom'] is not None else float('inf'))
    
    return phase_info

def make_phase_diagram_plotly(
    formulas: List[str],
    temp: int,
    api_key: str,
    ip: str,
    e_cut: float,
    functional: str = "GGA_GGA_U_R2SCAN",
) -> JSONResponse:

    # ─── validation ───────────────────────────────────────────
    if temp != 0 and not 300 <= temp <= 2000:
        raise HTTPException(status_code=400,
            detail="Temperature must be 0 K or between 300-2000 K. Please adjust the temperature setting.")
    if len(formulas) < 2:
        raise HTTPException(status_code=400, detail="At least 2 chemical formulas are required. Please add more formulas.")
    if len(formulas) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 formulas allowed. Please remove some formulas.")
    if e_cut < 0:
        raise HTTPException(status_code=400, detail="Energy cutoff must be greater than or equal to 0 eV/atom.")

    elements = _elements(formulas)

    # ─── functional mapping ─────────────────────────────────
    functional_map = {
        "GGA_GGA_U_R2SCAN": ["GGA_GGA+U", "R2SCAN"],
        "R2SCAN": ["R2SCAN"],
        "GGA_GGA_U": ["GGA_GGA+U"]
    }
    
    if functional not in functional_map:
        raise HTTPException(status_code=400, detail=f"Unsupported functional: {functional}. Supported: GGA_GGA_U_R2SCAN, R2SCAN, GGA_GGA_U")
    
    thermo_types = functional_map[functional]

    # ─── fetch Materials Project entries ─────────────────────
    with MPRester(api_key=api_key) as m:
        entries = (m.get_entries_in_chemsys(elements, additional_criteria={"thermo_types": thermo_types}) if temp == 0
                   else m.get_entries_in_chemsys(elements, use_gibbs=temp, additional_criteria={"thermo_types": thermo_types}))

    if not entries:
        raise HTTPException(status_code=404, detail=f"No materials found for elements {', '.join(elements)} in Materials Project database. Try different chemical formulas.")

    # ─── build phase diagram ─────────────────────────────────
    terminals = [Composition(f) for f in formulas[:len(formulas)]]
    pd = CompoundPhaseDiagram(entries, terminals, normalize_terminal_compositions=True)

    fig = PDPlotter(pd, backend="plotly", show_unstable=e_cut).get_plot()
    
    # Extract phase information with original entries for better data access
    phase_info = _extract_phase_info(pd, entries, temp)

    logger.info("PD  T=%dK  elems=%s  e_cut=%.3f  func=%s  keyHash=%s  ip=%s",
                temp, ",".join(elements), e_cut, functional, _hash_key(api_key), ip)

    # Combine plot data with phase information
    plot_data = json.loads(fig.to_json())
    response_data = {
        'plot': plot_data,
        'phase_info': phase_info,
        'metadata': {
            'temperature': temp,
            'elements': elements,
            'e_cut': e_cut,
            'functional': functional,
            'num_phases': len(phase_info)
        }
    }

    return JSONResponse(content=response_data)