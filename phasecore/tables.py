"""Reference tables used by the finite-temperature (Gibbs) model.

The tables are exported from pymatgen by ``scripts/export_reference_tables.py``
and loaded from ``phasecore/data``. Only the standard library is used so the module
runs unchanged in CPython and in the browser (Pyodide).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load(name: str) -> dict:
    """
    Read one JSON table from the data directory.

    Args:
        name: File name, e.g. ``"g_els.json"``.

    Returns:
        The parsed JSON content.
    """
    with open(_DATA_DIR / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


# {"300": {"Fe": -0.12, ...}, "400": {...}, ...}: elemental Gibbs energies (eV/atom).
G_ELEMS: Dict[str, Dict[str, float]] = _load("g_els.json")

# {"CO2": {"300": -4.1, ...}, ...}: experimental Gibbs energies of formation of gases (eV).
G_GASES: Dict[str, Dict[str, float]] = _load("nist_gas_gf.json")

# {"Fe": 55.845, ...}: atomic masses in amu.
ATOMIC_MASSES: Dict[str, float] = _load("elements.json")

# Temperatures (K) at which G_ELEMS is tabulated, ascending.
GIBBS_TEMPERATURES: List[float] = sorted(float(t) for t in G_ELEMS)

# Elements that have finite-temperature reference data.
GIBBS_ELEMENTS = frozenset(next(iter(G_ELEMS.values())))

# Finite-temperature model limits (K).
MIN_GIBBS_TEMPERATURE = 300
MAX_GIBBS_TEMPERATURE = 2000
