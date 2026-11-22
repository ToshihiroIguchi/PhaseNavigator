"""Phase diagram generation from a pre-downloaded dataset."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .entries import Dataset, Entry
from .formula import parse_formula
from .gibbs import check_temperature, gibbs_entries, unsupported_elements
from .hull import CompoundHull
from .plotting import build_figure

# Functional names used by the UI and the matching Materials Project thermo types.
FUNCTIONAL_THERMO_TYPES: Dict[str, str] = {
    "GGA_GGA_U_R2SCAN": "GGA_GGA+U_R2SCAN",
    "R2SCAN": "R2SCAN",
    "GGA_GGA_U": "GGA_GGA+U",
}

MIN_FORMULAS = 2
MAX_FORMULAS = 4
MAX_ENERGY_CUTOFF = 2.0


def _validate(formulas: Sequence[str], temperature: int, energy_cutoff: float, functional: str) -> List[str]:
    """
    Validate the request values.

    Args:
        formulas: Formulas as typed by the user.
        temperature: Temperature in kelvin (0 or 300-2000).
        energy_cutoff: Energy cutoff in eV/atom.
        functional: One of ``FUNCTIONAL_THERMO_TYPES``.

    Returns:
        The trimmed, non-empty formulas.

    Raises:
        ValueError: If any value is out of range or unsupported.
    """
    cleaned = [f.strip() for f in formulas if f.strip()]
    if len(cleaned) < MIN_FORMULAS:
        raise ValueError(f"At least {MIN_FORMULAS} chemical formulas are required")
    if len(cleaned) > MAX_FORMULAS:
        raise ValueError(f"Maximum {MAX_FORMULAS} formulas allowed")
    if functional not in FUNCTIONAL_THERMO_TYPES:
        raise ValueError(f"Unsupported functional: {functional}. Supported: {list(FUNCTIONAL_THERMO_TYPES)}")
    if temperature != 0:
        check_temperature(temperature)
    if not 0 <= energy_cutoff <= MAX_ENERGY_CUTOFF:
        raise ValueError(f"Energy cutoff must be between 0 and {MAX_ENERGY_CUTOFF} eV/atom")
    return cleaned


def phase_info(hull: CompoundHull, temperature: int) -> List[Dict[str, Any]]:
    """
    Describe the stable phases, most stable first.

    Args:
        hull: The phase diagram.
        temperature: Temperature in kelvin, copied into each row.

    Returns:
        One dict per stable phase, in the same shape as the server's ``PhaseInfo``.
    """
    rows = []
    for point in hull.stable_points:
        entry: Entry = point.entry
        rows.append(
            {
                "formula": entry.formula,
                "composition": entry.composition_string,
                "energy_per_atom": round(point.energy_per_atom, 4),
                "total_energy": round(point.energy, 4),
                "formation_energy_per_atom": round(hull.formation_energy_per_atom(point), 4),
                "correction": round(entry.correction, 4),
                "entry_id": entry.entry_id,
                "temperature": temperature,
                "num_atoms": entry.num_atoms,
            }
        )
    rows.sort(key=lambda row: (row["formation_energy_per_atom"], row["formula"], row["entry_id"]))
    return rows


def generate_diagram(
    dataset: Dataset,
    formulas: Sequence[str],
    temperature: int,
    energy_cutoff: float,
    functional: str,
) -> Dict[str, Any]:
    """
    Build a phase diagram from the bundled data.

    Args:
        dataset: Entries for the thermo type of ``functional``.
        formulas: Two to four terminal formulas.
        temperature: Temperature in kelvin; 0 for the 0 K enthalpy diagram.
        energy_cutoff: Unstable phases up to this energy above hull are plotted (eV/atom).
        functional: One of ``FUNCTIONAL_THERMO_TYPES``.

    Returns:
        A dict shaped like the server response: ``plot``, ``phase_info`` and ``metadata``.

    Raises:
        ValueError: With a user-facing message if the input is invalid, the data has
            no entries for the system, or finite-temperature data is missing.
    """
    cleaned = _validate(formulas, temperature, energy_cutoff, functional)
    terminals = [parse_formula(formula) for formula in cleaned]
    elements = sorted({el for terminal in terminals for el in terminal})

    if temperature > 0:
        missing = unsupported_elements(elements)
        if missing:
            raise ValueError(
                f"Finite-temperature data is not available for {', '.join(missing)}. "
                "Use 0 K or remove these elements."
            )

    entries = dataset.select(elements)
    if not entries:
        raise ValueError(f"No materials found for elements {elements} in the bundled data")
    if temperature > 0:
        entries = gibbs_entries(entries, temperature)

    hull = CompoundHull(entries, terminals, cleaned)
    rows = phase_info(hull, temperature)
    return {
        "plot": build_figure(hull, energy_cutoff),
        "phase_info": rows,
        "metadata": {
            "temperature": temperature,
            "elements": elements,
            "e_cut": energy_cutoff,
            "functional": functional,
            "num_phases": len(rows),
            "excluded_non_commercial": 0,
            "include_non_commercial": False,
            "data": {key: dataset.meta.get(key) for key in ("thermo_type", "retrieved_at", "database_version")},
        },
    }
