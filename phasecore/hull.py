"""Compound phase diagrams: convex hull in the space spanned by terminal formulas.

This reproduces what the server does with pymatgen's ``CompoundPhaseDiagram``
(``normalize_terminal_compositions=True``) using numpy and scipy only:

1. every entry is rewritten in terms of the terminal compositions (entries outside
   the space spanned by the terminals are dropped);
2. per composition only the lowest-energy entry is kept;
3. the lower convex hull of (composition, energy per atom) is computed with qhull
   using the same options as pymatgen (``"Qt i"`` plus an extra top point that marks
   the upper facets), so the same entries come out stable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.spatial import ConvexHull

from .entries import Entry

# Tolerances copied from pymatgen's PhaseDiagram / TransformedPDEntry.
AMOUNT_TOL = 1e-5
FORMATION_ENERGY_TOL = 1e-11
DETERMINANT_TOL = 1e-14
RESIDUAL_TOL = 1e-6


@dataclass(frozen=True, eq=False)
class Point:
    """
    An entry expressed in terminal coordinates.

    Attributes:
        entry: The original entry.
        fractions: Fraction of each terminal (sums to 1).
        energy_per_atom: Energy per atom in the terminal space (eV/atom).
        energy: Total energy of the entry (eV).
    """

    entry: Entry
    fractions: np.ndarray
    energy_per_atom: float
    energy: float


class CompoundHull:
    """Lower convex hull of entries in the space of terminal compositions."""

    def __init__(
        self,
        entries: Sequence[Entry],
        terminals: Sequence[Dict[str, float]],
        labels: Sequence[str],
    ) -> None:
        """
        Args:
            entries: Entries of the chemical system.
            terminals: Terminal compositions (element amounts), 2 to 4 of them.
            labels: Terminal formulas as the user typed them, used in error messages.

        Raises:
            ValueError: If the terminals are linearly dependent, or a terminal has no
                entry of its own composition.
        """
        self.labels = list(labels)
        self.dim = len(terminals)
        self.points = self._transform(entries, terminals)
        self._group()
        self._build_hull()

    # -- construction -----------------------------------------------------------------

    def _transform(self, entries: Sequence[Entry], terminals: Sequence[Dict[str, float]]) -> List[Point]:
        """
        Rewrite entries in terminal coordinates.

        Args:
            entries: Entries to transform.
            terminals: Terminal compositions.

        Returns:
            Points for the entries that lie inside the space spanned by the terminals.

        Raises:
            ValueError: If the terminals are linearly dependent.
        """
        elements = sorted({el for terminal in terminals for el in terminal})
        index = {el: i for i, el in enumerate(elements)}
        matrix = np.zeros((len(terminals), len(elements)))
        for row, terminal in enumerate(terminals):
            total = sum(terminal.values())
            for el, amount in terminal.items():
                matrix[row, index[el]] = amount / total
        if np.linalg.matrix_rank(matrix) < len(terminals):
            raise ValueError(
                "The formulas are linearly dependent (one can be made from the others), "
                "so they do not span a phase diagram. Choose independent formulas."
            )
        pseudo_inverse = np.linalg.pinv(matrix)

        points: List[Point] = []
        for entry in entries:
            if not entry.elements <= set(elements):
                continue
            vector = np.zeros(len(elements))
            for el, amount in entry.composition.items():
                vector[index[el]] = amount
            amounts = vector @ pseudo_inverse
            if np.abs(vector - amounts @ matrix).max() > RESIDUAL_TOL:
                continue  # not a combination of the terminals
            if (amounts < -AMOUNT_TOL).any():
                continue  # needs a negative amount of a terminal
            amounts = np.where(amounts > AMOUNT_TOL, amounts, 0.0)
            total = float(amounts.sum())
            points.append(Point(entry, amounts / total, entry.energy / total, entry.energy))
        return points

    def _group(self) -> None:
        """Keep the lowest-energy point per composition and find the terminal references."""
        best: Dict[Tuple[float, ...], Point] = {}
        for point in self.points:
            key = tuple(np.round(point.fractions, 8))
            current = best.get(key)
            if current is None or (point.energy_per_atom, point.entry.entry_id) < (
                current.energy_per_atom,
                current.entry.entry_id,
            ):
                best[key] = point
        self.min_points = sorted(best.values(), key=lambda p: (tuple(np.round(p.fractions, 8)), p.energy_per_atom, p.entry.entry_id))

        self.references: List[Point] = []
        for i, label in enumerate(self.labels):
            corner = tuple(np.round(np.eye(self.dim)[i], 8))
            point = best.get(corner)
            if point is None:
                raise ValueError(f"No entry found for '{label}' in the selected data.")
            self.references.append(point)
        self.reference_energies = np.array([p.energy_per_atom for p in self.references])

    def _build_hull(self) -> None:
        """Compute the lower convex hull, its facets and the stable points."""
        fractions = np.array([p.fractions for p in self.min_points])
        energies = np.array([p.energy_per_atom for p in self.min_points])
        formation = energies - fractions @ self.reference_energies

        chosen = [i for i, value in enumerate(formation) if value < -FORMATION_ENERGY_TOL]
        reference_ids = {id(p) for p in self.references}
        chosen.extend(i for i, p in enumerate(self.min_points) if id(p) in reference_ids)

        self.hull_points: List[Point] = [self.min_points[i] for i in chosen]
        data = np.column_stack([fractions[chosen][:, 1:], energies[chosen]])

        extra = np.zeros(self.dim) + 1.0 / self.dim
        extra[-1] = data.max() + 1.0
        data = np.vstack([data, extra])

        simplices = ConvexHull(data, qhull_options="Qt i").simplices
        facets: List[List[int]] = []
        for facet in simplices:
            if max(facet) == len(data) - 1:
                continue  # touches the extra point: an upper facet
            matrix = data[facet].copy()
            matrix[:, -1] = 1.0
            if abs(np.linalg.det(matrix)) > DETERMINANT_TOL:
                facets.append([int(i) for i in facet])
        self.facets = facets
        self.hull_data = data[:-1]
        self.stable_points: List[Point] = [
            self.hull_points[i] for i in sorted({i for facet in facets for i in facet})
        ]

        # Each lower facet lies in a plane E = slope . x + intercept. The hull is the
        # upper envelope of those planes, so its energy anywhere is their maximum.
        planes = np.zeros((len(facets), self.dim))
        for row, facet in enumerate(facets):
            matrix = np.column_stack([data[facet][:, :-1], np.ones(len(facet))])
            planes[row] = np.linalg.solve(matrix, data[facet][:, -1])
        self._planes = planes

    # -- queries ----------------------------------------------------------------------

    def formation_energy_per_atom(self, point: Point) -> float:
        """
        Formation energy per atom relative to the terminal references.

        Args:
            point: A point of this diagram.

        Returns:
            Energy per atom minus the fraction-weighted reference energies (eV/atom).
        """
        return float(point.energy_per_atom - point.fractions @ self.reference_energies)

    def energy_above_hull(self, points: Sequence[Point]) -> np.ndarray:
        """
        Energy of points above the convex hull.

        Args:
            points: Points of this diagram.

        Returns:
            Array of energies above hull in eV/atom (0 for stable points).
        """
        if not points:
            return np.zeros(0)
        coords = np.array([p.fractions[1:] for p in points])
        energies = np.array([p.energy_per_atom for p in points])
        hull = (coords @ self._planes[:, :-1].T + self._planes[:, -1]).max(axis=1)
        above = energies - hull
        stable = {id(p) for p in self.stable_points}
        return np.array([0.0 if id(p) in stable else value for p, value in zip(points, above)])
