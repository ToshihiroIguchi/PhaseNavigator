"""Export the pymatgen reference tables that the static calculation core needs.

The finite-temperature (Gibbs) model needs three small tables that ship with
pymatgen: elemental Gibbs energies, experimental NIST-JANAF gas data, and atomic
masses. They are copied into ``phasecore/data`` so that the browser build does not
depend on pymatgen. Re-run this script after upgrading pymatgen and commit the
result; ``tests/test_phasecore_tables.py`` checks that the copies stay in sync.

Usage (from the repository root, inside the project virtual environment)::

    python -m scripts.export_reference_tables
"""
import json
from pathlib import Path
from typing import Dict

from pymatgen.analysis.compatibility.computed_entries import G_ELEMS, G_GASES
from pymatgen.core.periodic_table import Element

DATA_DIR = Path(__file__).resolve().parent.parent / "phasecore" / "data"


def atomic_masses() -> Dict[str, float]:
    """
    Collect atomic masses for every element pymatgen knows.

    Returns:
        Mapping from element symbol to atomic mass in amu.
    """
    masses: Dict[str, float] = {}
    for element in Element:
        mass = element.atomic_mass
        if mass is not None:
            masses[element.symbol] = float(mass)
    return masses


def write_json(name: str, payload: object) -> None:
    """
    Write a JSON file into the data directory with stable formatting.

    Args:
        name: File name inside ``phasecore/data``.
        payload: JSON-serializable content.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, sort_keys=False, separators=(",", ":"))
        handle.write("\n")
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> None:
    """Export all reference tables."""
    write_json("g_els.json", G_ELEMS)
    write_json("nist_gas_gf.json", G_GASES)
    write_json("elements.json", atomic_masses())


if __name__ == "__main__":
    main()
