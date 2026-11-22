"""Computed entries and the pre-downloaded dataset they are loaded from."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

# Layout of one record in a dataset file. Keep in sync with scripts/build_static_data.py.
RECORD_FIELDS: Tuple[str, ...] = (
    "entry_id",
    "composition",
    "energy",
    "correction",
    "volume_per_atom",
    "formula",
    "gas_formula",
    "gas_factor",
)

SCHEMA_VERSION = 1


def format_amount(amount: float, tol: float = 1e-8) -> str:
    """
    Format an element amount the way pymatgen prints compositions.

    Args:
        amount: The amount of one element.
        tol: Distance to an integer below which the amount counts as that integer.

    Returns:
        An integer string, or the amount rounded to 8 decimals.
    """
    if abs(round(amount) - amount) < tol:
        return str(int(round(amount)))
    return str(round(amount, 8))


@dataclass(frozen=True, eq=False)
class Entry:
    """
    One computed material.

    Attributes:
        entry_id: Materials Project entry ID including the functional suffix.
        composition: Element amounts of the calculated cell, in structure order.
        energy: Total energy of the cell in eV, including corrections.
        correction: Part of ``energy`` that is an empirical correction (eV).
        volume_per_atom: Cell volume per atom in cubic angstrom.
        formula: Reduced formula in pymatgen's electronegativity ordering.
        gas_formula: Integer formula when NIST-JANAF gas data replaces this entry at
            finite temperature, otherwise ``None``.
        gas_factor: Cell amount divided by ``gas_formula``; ``None`` for non-gases.
    """

    entry_id: str
    composition: Dict[str, float]
    energy: float
    correction: float
    volume_per_atom: float
    formula: str
    gas_formula: Optional[str] = None
    gas_factor: Optional[float] = None

    @property
    def num_atoms(self) -> float:
        """Number of atoms in the cell composition."""
        return float(sum(self.composition.values()))

    @property
    def energy_per_atom(self) -> float:
        """Total energy divided by the number of atoms (eV/atom)."""
        return self.energy / self.num_atoms

    @property
    def elements(self) -> FrozenSet[str]:
        """Element symbols present in the entry."""
        return frozenset(self.composition)

    @property
    def is_element(self) -> bool:
        """True if the entry is a pure element."""
        return len(self.composition) == 1

    @property
    def composition_string(self) -> str:
        """Composition text such as ``"Fe4 O6"`` (same format as pymatgen)."""
        return " ".join(f"{el}{format_amount(amt)}" for el, amt in self.composition.items())

    def replaced(self, **changes: Any) -> "Entry":
        """
        Copy this entry with some fields changed.

        Args:
            **changes: Field names and their new values.

        Returns:
            A new entry.
        """
        values = {name: getattr(self, name) for name in RECORD_FIELDS}
        values.update(changes)
        return Entry(**values)

    @classmethod
    def from_record(cls, record: Sequence[Any]) -> "Entry":
        """
        Build an entry from a dataset record.

        Args:
            record: A list laid out as ``RECORD_FIELDS``.

        Returns:
            The entry.
        """
        values = dict(zip(RECORD_FIELDS, record))
        values["composition"] = {el: float(amt) for el, amt in values["composition"].items()}
        return cls(**values)


class Dataset:
    """A pre-downloaded set of entries for one thermo type."""

    def __init__(self, records: List[Sequence[Any]], meta: Dict[str, Any]) -> None:
        """
        Args:
            records: Dataset records laid out as ``RECORD_FIELDS``.
            meta: Descriptive fields stored next to the records (thermo type, dates, ...).
        """
        self.records = records
        self.meta = meta
        self._element_sets: List[FrozenSet[str]] = [frozenset(rec[1]) for rec in records]

    def __len__(self) -> int:
        return len(self.records)

    @classmethod
    def from_json(cls, text: str) -> "Dataset":
        """
        Parse the JSON text of a dataset file.

        Args:
            text: File content produced by ``scripts/build_static_data.py``.

        Returns:
            The dataset.

        Raises:
            ValueError: If the schema version or the record layout is not supported.
        """
        payload = json.loads(text)
        if payload.get("schema") != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported dataset schema {payload.get('schema')!r}; expected {SCHEMA_VERSION}."
            )
        if tuple(payload.get("fields", ())) != RECORD_FIELDS:
            raise ValueError("Dataset record layout does not match this version of the calculation core.")
        meta = {key: value for key, value in payload.items() if key != "entries"}
        return cls(payload["entries"], meta)

    def select(self, elements: Iterable[str]) -> List[Entry]:
        """
        Pick the entries whose elements are all in the given set.

        Args:
            elements: Element symbols of the chemical system.

        Returns:
            Entries of the system and of all its subsystems.
        """
        allowed = frozenset(elements)
        return [
            Entry.from_record(record)
            for record, present in zip(self.records, self._element_sets)
            if present <= allowed
        ]
