"""Synthetic computed entries for comparing ``phasecore`` with pymatgen.

The numbers are invented (they only look like real data): the point is to give both
implementations identical input, never to reproduce Materials Project values.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from pymatgen.core import Lattice, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry

from phasecore.entries import Dataset
from scripts.build_static_data import entry_to_record
from phasecore.entries import RECORD_FIELDS, SCHEMA_VERSION

# Energy per atom of the lowest elemental entries; compound energies are built from them.
REFERENCE_ENERGY = {"Fe": -8.30, "Al": -3.75, "O": -4.95, "C": -9.20, "H": -3.40, "N": -8.30}

# (entry id, element amounts of the cell, value, volume per atom, correction per atom).
# For elements ``value`` is the energy per atom; for compounds it is the formation
# energy per atom relative to the lowest elemental entries.
Spec = Tuple[str, Dict[str, int], float, float, float]

SPECS: List[Spec] = [
    # Elements. Two polymorphs for Fe and O so the lowest one must be chosen.
    ("mp-1-GGA", {"Fe": 2}, -8.30, 11.8, 0.0),
    ("mp-2-GGA", {"Fe": 4}, -8.27, 12.4, 0.0),
    ("mp-3-GGA", {"Al": 4}, -3.75, 16.5, 0.0),
    ("mp-4-GGA", {"O": 2}, -4.95, 17.0, 0.0),
    ("mp-5-GGA", {"O": 4}, -4.93, 18.2, 0.0),
    ("mp-6-GGA", {"C": 2}, -9.20, 8.8, 0.0),
    ("mp-7-GGA", {"H": 2}, -3.40, 25.0, 0.0),
    ("mp-8-GGA", {"N": 2}, -8.30, 20.0, 0.0),
    # Fe-Al-O. FeAlO3 lies between Fe2O3 and Al2O3; Fe3O4 and FeAl2O4 are interior
    # phases of the FeO-Fe2O3-Al2O3 diagram.
    ("mp-10-GGA+U", {"Fe": 4, "O": 6}, -1.05, 10.4, -0.41),
    ("mp-11-GGA+U", {"Fe": 2, "O": 2}, -0.95, 10.9, -0.34),
    ("mp-12-GGA+U", {"Fe": 3, "O": 4}, -1.06, 10.8, -0.39),
    ("mp-13-GGA", {"Al": 4, "O": 6}, -3.00, 8.6, -0.52),
    ("mp-14-GGA+U", {"Fe": 2, "Al": 4, "O": 8}, -2.55, 9.6, -0.45),
    ("mp-15-GGA+U", {"Fe": 2, "Al": 2, "O": 6}, -2.20, 10.0, -0.43),
    ("mp-16-GGA", {"Fe": 2, "Al": 2}, -0.28, 13.0, 0.0),
    ("mp-17-GGA", {"Fe": 3, "Al": 1}, -0.12, 12.0, 0.0),
    ("mp-18-GGA", {"Fe": 2, "Al": 5}, -0.27, 14.5, 0.0),
    ("mp-19-GGA", {"Fe": 1, "Al": 3}, 0.05, 15.0, 0.0),  # positive formation energy
    # C-O and C compounds. CO2 and CO match NIST-JANAF gas data.
    ("mp-20-GGA", {"C": 4, "O": 8}, -1.45, 22.0, -0.30),
    ("mp-21-GGA", {"C": 2, "O": 2}, -0.95, 19.0, -0.28),
    ("mp-22-GGA", {"C": 2, "O": 1}, -0.20, 14.0, 0.0),
    ("mp-23-GGA", {"Fe": 3, "C": 1}, 0.02, 11.0, 0.0),
    ("mp-24-GGA", {"Al": 4, "C": 3}, -0.25, 12.0, 0.0),
    ("mp-25-GGA+U", {"Fe": 1, "C": 1, "O": 3}, -1.30, 14.0, -0.37),
    ("mp-26-GGA", {"Al": 2, "C": 1, "O": 4}, -1.60, 12.5, -0.41),
    # H-O. H2O matches gas data, H2O2 does not.
    ("mp-30-GGA", {"H": 4, "O": 2}, -1.00, 20.0, -0.20),
    ("mp-31-GGA", {"H": 2, "O": 2}, -0.70, 19.0, 0.0),
]


def make_entry(spec: Spec) -> ComputedStructureEntry:
    """
    Build a pymatgen entry from a spec.

    Args:
        spec: One item of ``SPECS``.

    Returns:
        A ``ComputedStructureEntry`` whose structure has the requested composition and
        volume per atom, and whose corrected energy matches the spec.
    """
    entry_id, amounts, value, volume_per_atom, correction_per_atom = spec
    total = sum(amounts.values())
    if len(amounts) == 1:
        energy_per_atom = value
    else:
        energy_per_atom = value + sum(n * REFERENCE_ENERGY[el] for el, n in amounts.items()) / total
    species = [el for el, n in amounts.items() for _ in range(n)]
    n_atoms = len(species)
    edge = (n_atoms * volume_per_atom) ** (1 / 3)
    coords = [[i / n_atoms, (i * i * 0.13) % 1.0, (i * 0.29) % 1.0] for i in range(n_atoms)]
    structure = Structure(Lattice.cubic(edge), species, coords)
    correction = correction_per_atom * n_atoms
    return ComputedStructureEntry(
        structure,
        energy_per_atom * n_atoms - correction,
        correction=correction,
        entry_id=entry_id,
    )


def make_entries() -> List[ComputedStructureEntry]:
    """
    Build every synthetic entry.

    Returns:
        pymatgen entries for all of ``SPECS``.
    """
    return [make_entry(spec) for spec in SPECS]


def make_dataset(entries: List[ComputedStructureEntry]) -> Dataset:
    """
    Convert entries into a ``phasecore`` dataset through the real JSON layout.

    Args:
        entries: pymatgen entries.

    Returns:
        The dataset, after a JSON round trip like a downloaded file would take.
    """
    payload = {
        "schema": SCHEMA_VERSION,
        "fields": list(RECORD_FIELDS),
        "thermo_type": "GGA_GGA+U",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "database_version": "test",
        "entries": [entry_to_record(entry) for entry in entries],
    }
    return Dataset.from_json(json.dumps(payload))
