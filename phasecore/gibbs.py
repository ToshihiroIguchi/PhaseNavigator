"""Finite-temperature free energies (Bartel et al., Nat. Commun. 9, 4168, 2018).

This reproduces pymatgen's ``GibbsComputedStructureEntry.from_entries`` using only
numpy, so it can run in the browser. The model:

    G(T) = N * (dH_f + G_delta(V, m, T)) - sum_i n_i * G_i(T)

where ``dH_f`` is the 0 K formation enthalpy per atom from the elemental references,
``G_delta`` is the SISSO descriptor, and ``G_i`` are elemental Gibbs energies. Entries
whose formula is a gas with NIST-JANAF data use the tabulated experimental value
instead. Only the descriptor-based part applies to solids, so the model is only
meant for solid phases.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import gcd, log
from typing import Dict, List, Sequence

import numpy as np

from .entries import Entry
from .tables import (
    ATOMIC_MASSES,
    G_ELEMS,
    G_GASES,
    GIBBS_ELEMENTS,
    MAX_GIBBS_TEMPERATURE,
    MIN_GIBBS_TEMPERATURE,
)

EXPERIMENTAL_SUFFIX = " (Experimental)"

# Elemental Gibbs energies regrouped per element: {"Fe": {"300": ..., "400": ...}, ...}.
_ELEMENT_SERIES: Dict[str, Dict[str, float]] = {
    element: {temp: values[element] for temp, values in G_ELEMS.items()}
    for element in GIBBS_ELEMENTS
}


def check_temperature(temperature: float) -> None:
    """
    Check that a temperature is inside the range of the Gibbs model.

    Args:
        temperature: Temperature in kelvin.

    Raises:
        ValueError: If it is outside 300-2000 K.
    """
    if temperature < MIN_GIBBS_TEMPERATURE or temperature > MAX_GIBBS_TEMPERATURE:
        raise ValueError(
            f"Temperature must be 0 K or between {MIN_GIBBS_TEMPERATURE}-{MAX_GIBBS_TEMPERATURE} K"
        )


def unsupported_elements(elements: Sequence[str]) -> List[str]:
    """
    List elements without finite-temperature reference data.

    Args:
        elements: Element symbols.

    Returns:
        Sorted symbols that are missing from the elemental Gibbs energy table.
    """
    return sorted(set(elements) - GIBBS_ELEMENTS)


def _interpolate(table: Dict[str, float], temperature: float) -> float:
    """
    Read a tabulated value at a temperature, linearly interpolating between rows.

    Args:
        table: Mapping from temperature string (K) to value.
        temperature: Temperature in kelvin.

    Returns:
        The value at ``temperature``.
    """
    if float(temperature) % 100 == 0 and str(int(temperature)) in table:
        return table[str(int(temperature))]
    xs = sorted(float(t) for t in table)
    ys = [table[str(int(t))] for t in xs]
    return float(np.interp(temperature, xs, ys))


def sum_elemental_gibbs(composition: Dict[str, float], temperature: float) -> float:
    """
    Sum the elemental Gibbs energies of a composition.

    Args:
        composition: Element amounts.
        temperature: Temperature in kelvin.

    Returns:
        ``sum_i n_i * G_i(T)`` in eV.
    """
    total = 0.0
    for element, amount in composition.items():
        total += amount * _interpolate(_ELEMENT_SERIES[element], temperature)
    return total


def _reduce(composition: Dict[str, float]) -> Dict[str, float]:
    """
    Divide a composition by the greatest common divisor of its amounts.

    Args:
        composition: Element amounts.

    Returns:
        The reduced composition.
    """
    fractions = {el: Fraction(amt).limit_denominator(10000) for el, amt in composition.items()}
    denominator = 1
    for value in fractions.values():
        denominator = denominator * value.denominator // gcd(denominator, value.denominator)
    numerators = [int(value * denominator) for value in fractions.values()]
    divisor = 0
    for numerator in numerators:
        divisor = gcd(divisor, numerator)
    divisor = divisor or 1
    return {el: float(int(value * denominator) // divisor) for el, value in fractions.items()}


def reduced_mass(composition: Dict[str, float]) -> float:
    """
    Reduced mass of Eq. 6 in Bartel et al. (2018).

    Args:
        composition: Element amounts of a compound (at least two elements).

    Returns:
        Reduced mass in amu.
    """
    reduced = _reduce(composition)
    n_elements = len(reduced)
    denominator = (n_elements - 1) * sum(reduced.values())
    mass_sum = 0.0
    for (el_i, alpha_i), (el_j, alpha_j) in combinations(reduced.items(), 2):
        m_i, m_j = ATOMIC_MASSES[el_i], ATOMIC_MASSES[el_j]
        mass_sum += (alpha_i + alpha_j) * (m_i * m_j) / (m_i + m_j)
    return mass_sum / denominator


def g_delta_sisso(volume_per_atom: float, mass: float, temperature: float) -> float:
    """
    Evaluate the SISSO descriptor G_delta (Eq. 4 in Bartel et al., 2018).

    Args:
        volume_per_atom: Volume per atom in cubic angstrom.
        mass: Reduced mass in amu.
        temperature: Temperature in kelvin.

    Returns:
        G_delta in eV/atom.
    """
    return (
        (-2.48e-4 * log(volume_per_atom) - 8.94e-5 * mass / volume_per_atom) * temperature
        + 0.181 * log(temperature)
        - 0.882
    )


def elemental_references(entries: Sequence[Entry]) -> Dict[str, Entry]:
    """
    Pick the lowest-energy elemental entry of each element.

    Args:
        entries: Entries of one chemical system.

    Returns:
        Mapping from element symbol to its reference entry.

    Raises:
        ValueError: If an element occurs in compounds but has no elemental entry.
    """
    references: Dict[str, Entry] = {}
    for entry in entries:
        if not entry.is_element:
            continue
        element = next(iter(entry.composition))
        best = references.get(element)
        if best is None or (entry.energy_per_atom, entry.entry_id) < (best.energy_per_atom, best.entry_id):
            references[element] = entry

    present = {el for entry in entries for el in entry.composition}
    missing = sorted(present - set(references))
    if missing:
        raise ValueError(f"No elemental reference entry found for {', '.join(missing)}.")
    return references


def gibbs_entries(entries: Sequence[Entry], temperature: float) -> List[Entry]:
    """
    Convert 0 K entries into free-energy entries at a temperature.

    Mirrors ``GibbsComputedStructureEntry.from_entries``: elemental entries other than
    the reference of each element are dropped, the references get zero energy, and
    every compound gets its Gibbs free energy of formation.

    Args:
        entries: 0 K entries of one chemical system and its subsystems.
        temperature: Temperature in kelvin, between 300 and 2000.

    Returns:
        New entries whose ``energy`` is the free energy (eV) and ``correction`` is 0.

    Raises:
        ValueError: If the temperature is out of range, an element has no
            finite-temperature data, or an elemental reference is missing.
    """
    check_temperature(temperature)
    missing = unsupported_elements(sorted({el for entry in entries for el in entry.composition}))
    if missing:
        raise ValueError(
            f"Finite-temperature data is not available for {', '.join(missing)}. "
            "Use 0 K or remove these elements."
        )

    references = elemental_references(entries)
    reference_ids = {id(entry) for entry in references.values()}
    reference_energy = {el: entry.energy_per_atom for el, entry in references.items()}

    converted: List[Entry] = []
    for entry in entries:
        if entry.is_element:
            if id(entry) not in reference_ids:
                continue
            converted.append(entry.replaced(energy=0.0, correction=0.0))
            continue

        entry_id = entry.entry_id
        if entry.gas_formula is not None:
            series = G_GASES[entry.gas_formula]
            energy = _interpolate(series, temperature) * float(entry.gas_factor)
            if "Experimental" not in entry_id:
                entry_id = f"{entry_id}{EXPERIMENTAL_SUFFIX}"
        else:
            num_atoms = entry.num_atoms
            formation_enthalpy = (
                entry.energy - sum(amt * reference_energy[el] for el, amt in entry.composition.items())
            ) / num_atoms
            delta = g_delta_sisso(entry.volume_per_atom, reduced_mass(entry.composition), temperature)
            energy = num_atoms * (formation_enthalpy + delta) - sum_elemental_gibbs(entry.composition, temperature)
        converted.append(entry.replaced(entry_id=entry_id, energy=energy, correction=0.0))
    return converted
