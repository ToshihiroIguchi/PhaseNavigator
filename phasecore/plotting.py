"""Plotly figures (as plain dicts) for compound phase diagrams.

Binary systems get a formation-energy hull, ternary systems a triangular composition
diagram and quaternary systems a tetrahedron. The styling follows the figures that
pymatgen's ``PDPlotter`` draws for the server version: black tie lines, green stable
phases and diamonds coloured by energy above hull for unstable phases.
"""
from __future__ import annotations

import math
import re
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from .hull import CompoundHull, Point

STABLE_COLOR = "#2e8b57"
LINE_COLOR = "#000000"
COLORSCALE = [[0.0, "#f6c98a"], [0.5, "#f2a65a"], [1.0, "#b8312f"]]
COLORBAR_TITLE = "Energy Above Hull<br>(eV/atom)"

# Corners of a regular tetrahedron with unit edges.
_TETRAHEDRON = np.array(
    [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.5, math.sqrt(3) / 2, 0.0],
        [0.5, math.sqrt(3) / 6, math.sqrt(2.0 / 3.0)],
    ]
)


def htmlify(formula: str) -> str:
    """
    Put the numbers of a formula in subscript tags.

    Args:
        formula: Formula such as ``"Fe2O3"``.

    Returns:
        HTML such as ``"Fe<sub>2</sub>O<sub>3</sub>"``.
    """
    return re.sub(r"(\d+(?:\.\d+)?)", r"<sub>\1</sub>", formula)


def _hover(hull: CompoundHull, point: Point, above: float) -> str:
    """
    Build the hover text of one phase.

    Args:
        hull: The phase diagram.
        point: The phase.
        above: Its energy above hull (eV/atom).

    Returns:
        HTML text for Plotly.
    """
    return (
        f"{htmlify(point.entry.formula)}<br>{point.entry.entry_id}<br>"
        f"Formation energy: {hull.formation_energy_per_atom(point):.4f} eV/atom<br>"
        f"Energy above hull: {above:.4f} eV/atom"
    )


def _unstable(hull: CompoundHull, cutoff: float) -> Tuple[List[Point], np.ndarray]:
    """
    Select the unstable phases that are within the energy cutoff.

    Args:
        hull: The phase diagram.
        cutoff: Largest energy above hull to show (eV/atom).

    Returns:
        The phases and their energies above hull.
    """
    stable_ids = {id(p) for p in hull.stable_points}
    candidates = [p for p in hull.min_points if id(p) not in stable_ids]
    above = hull.energy_above_hull(candidates)
    keep = [i for i, value in enumerate(above) if value <= cutoff]
    return [candidates[i] for i in keep], above[keep]


def _edges(hull: CompoundHull) -> List[Tuple[Point, Point]]:
    """
    List every tie line of the hull once.

    Args:
        hull: The phase diagram.

    Returns:
        Pairs of stable phases that share a facet.
    """
    seen: Set[Tuple[int, int]] = set()
    edges: List[Tuple[Point, Point]] = []
    for facet in hull.facets:
        for i, j in combinations(sorted(facet), 2):
            if (i, j) not in seen:
                seen.add((i, j))
                edges.append((hull.hull_points[i], hull.hull_points[j]))
    return edges


def _terminal_labels(hull: CompoundHull) -> List[str]:
    """
    Name the terminals by the reduced formula of their reference entries.

    Args:
        hull: The phase diagram.

    Returns:
        HTML labels, one per terminal.
    """
    return [htmlify(p.entry.formula) for p in hull.references]


def _marker_group(
    name: str,
    points: Sequence[Point],
    above: np.ndarray,
    hull: CompoundHull,
    cutoff: float,
    stable: bool,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """
    Marker properties shared by every dimensionality.

    Args:
        name: Legend name.
        points: Phases to mark.
        above: Their energies above hull.
        hull: The phase diagram.
        cutoff: Upper limit of the colour scale (eV/atom).
        stable: True for the stable group.
        scale: Factor applied to the marker sizes (3D markers look larger than 2D ones).

    Returns:
        Keys to merge into a Plotly trace.
    """
    marker: Dict[str, Any]
    if stable:
        marker = {"color": STABLE_COLOR, "size": 12 * scale, "symbol": "circle", "line": {"color": "#ffffff", "width": 1}}
    else:
        marker = {
            "color": [float(v) for v in above],
            "colorscale": COLORSCALE,
            "cmin": 0.0,
            "cmax": max(cutoff, 1e-6),
            "size": 7 * scale,
            "symbol": "diamond",
            "line": {"color": "#666666", "width": 0.5},
            "colorbar": {"title": {"text": COLORBAR_TITLE}, "thickness": 14, "len": 0.6},
        }
    return {
        "name": name,
        "marker": marker,
        "hovertext": [_hover(hull, p, float(a)) for p, a in zip(points, above)],
        "hoverinfo": "text",
    }


def _base_layout() -> Dict[str, Any]:
    """
    Layout settings shared by all figures.

    Returns:
        A Plotly layout dict.
    """
    return {
        "autosize": True,
        "hovermode": "closest",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "showlegend": True,
        "legend": {"orientation": "h", "x": 0, "xanchor": "left", "y": 1.08},
        "margin": {"b": 40, "l": 50, "r": 20, "t": 40},
    }


def build_figure(hull: CompoundHull, cutoff: float) -> Dict[str, Any]:
    """
    Build the Plotly figure of a phase diagram.

    Args:
        hull: The phase diagram (2 to 4 terminals).
        cutoff: Unstable phases up to this energy above hull (eV/atom) are drawn.

    Returns:
        A dict with ``data`` and ``layout`` keys ready for ``Plotly.newPlot``.

    Raises:
        ValueError: If the diagram has an unsupported number of terminals.
    """
    if hull.dim == 2:
        return _binary(hull, cutoff)
    if hull.dim == 3:
        return _ternary(hull, cutoff)
    if hull.dim == 4:
        return _quaternary(hull, cutoff)
    raise ValueError("Phase diagrams are supported for 2 to 4 formulas.")


def _binary(hull: CompoundHull, cutoff: float) -> Dict[str, Any]:
    """Formation energy against the fraction of the second terminal."""
    stable = sorted(hull.stable_points, key=lambda p: float(p.fractions[1]))
    above_stable = np.zeros(len(stable))
    unstable, above = _unstable(hull, cutoff)

    def xy(points: Sequence[Point]) -> Tuple[List[float], List[float]]:
        return (
            [float(p.fractions[1]) for p in points],
            [hull.formation_energy_per_atom(p) for p in points],
        )

    sx, sy = xy(stable)
    ux, uy = xy(unstable)
    inner = [p for p in stable if not (np.isclose(p.fractions, np.eye(2)).all(axis=1).any())]
    ix, iy = xy(inner)
    low = min(sy + uy + [0.0])
    data: List[Dict[str, Any]] = [
        {"type": "scatter", "mode": "lines", "x": sx, "y": sy, "line": {"color": LINE_COLOR, "width": 3},
         "hoverinfo": "none", "showlegend": False},
        {"type": "scatter", "mode": "text", "name": "Labels (stable)", "x": ix, "y": [v - 0.04 * max(1e-9, -low) - 0.01 for v in iy],
         "text": [htmlify(p.entry.formula) for p in inner], "textposition": "bottom center",
         "hoverinfo": "skip", "showlegend": False},
        {"type": "scatter", "mode": "markers", "x": sx, "y": sy, **_marker_group("Stable", stable, above_stable, hull, cutoff, True)},
        {"type": "scatter", "mode": "markers", "x": ux, "y": uy, **_marker_group("Above Hull", unstable, above, hull, cutoff, False)},
    ]
    labels = _terminal_labels(hull)
    layout = _base_layout()
    layout.update(
        {
            "xaxis": {"title": {"text": "Composition"}, "range": [-0.08, 1.08], "zeroline": False,
                      "tickvals": [0, 1], "ticktext": labels, "showgrid": False},
            "yaxis": {"title": {"text": "Formation energy (eV/atom)"}, "zeroline": True,
                      "gridcolor": "rgba(0,0,0,0.08)"},
        }
    )
    return {"data": data, "layout": layout}


# Estimated size of a ternary diagram in pixels, used to judge how much room a label needs.
_TERNARY_SIDE_PX = 600.0
_LABEL_FONT_PX = 13.0
_LABEL_POSITIONS = (
    "middle right", "middle left", "top center", "bottom center",
    "top right", "top left", "bottom right", "bottom left",
)


def _ternary_xy(fractions: Sequence[float]) -> Tuple[float, float]:
    """
    Convert ternary fractions to Cartesian coordinates of the triangle.

    In Plotly's layout the first terminal is the top corner, the second the bottom-left
    and the third the bottom-right; the side length is 1.

    Args:
        fractions: Fractions of the first three terminals.

    Returns:
        The ``(x, y)`` position.
    """
    top, _left, right = (float(v) for v in fractions[:3])
    return right + top / 2, top * math.sqrt(3) / 2


def _label_box(
    x: float, y: float, position: str, width: float, height: float, gap: float
) -> Tuple[float, float, float, float]:
    """
    Estimate the box a label occupies for one Plotly ``textposition``.

    Args:
        x: Marker x position.
        y: Marker y position.
        position: A value of ``_LABEL_POSITIONS``.
        width: Label width in triangle units.
        height: Label height in triangle units.
        gap: Distance kept between the marker and the label.

    Returns:
        ``(x0, y0, x1, y1)`` of the box.
    """
    vertical, horizontal = position.split()
    if horizontal == "right":
        x0 = x + gap
    elif horizontal == "left":
        x0 = x - gap - width
    else:
        x0 = x - width / 2
    if vertical == "top":
        y0 = y + gap
    elif vertical == "bottom":
        y0 = y - gap - height
    else:
        y0 = y - height / 2
    return x0, y0, x0 + width, y0 + height


def _label_penalty(
    box: Tuple[float, float, float, float],
    placed: Sequence[Tuple[float, float, float, float]],
    markers: Sequence[Tuple[float, float]],
    segments: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
    marker_radius: float,
) -> float:
    """
    Score a label box; the lower the score, the less it collides with.

    Args:
        box: Candidate label box.
        placed: Boxes of the labels that are already placed.
        markers: Positions of the other markers.
        segments: Tie lines as pairs of end points.
        marker_radius: Radius of a marker in triangle units.

    Returns:
        A non-negative penalty.
    """
    x0, y0, x1, y1 = box
    penalty = 0.0
    for a0, b0, a1, b1 in placed:
        overlap_x = min(x1, a1) - max(x0, a0)
        overlap_y = min(y1, b1) - max(y0, b0)
        if overlap_x > 0 and overlap_y > 0:
            penalty += 100.0 + 1e5 * overlap_x * overlap_y
    for mx, my in markers:
        if x0 - marker_radius < mx < x1 + marker_radius and y0 - marker_radius < my < y1 + marker_radius:
            penalty += 60.0
    for (sx, sy), (ex, ey) in segments:
        hits = 0
        for k in range(25):
            t = k / 24
            px, py = sx + (ex - sx) * t, sy + (ey - sy) * t
            if x0 <= px <= x1 and y0 <= py <= y1:
                hits += 1
        if hits:
            penalty += 10.0 + hits
    tolerance = 0.003
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        outside = (
            cy < -tolerance
            or math.sqrt(3) * cx - cy < -tolerance * 2
            or math.sqrt(3) * (1 - cx) - cy < -tolerance * 2
        )
        if outside:
            penalty += 30.0
    return penalty


def _place_ternary_labels(
    points: Sequence[Point], edges: Sequence[Tuple[Point, Point]]
) -> List[Tuple[str, str]]:
    """
    Choose a position for every phase label so that labels avoid each other.

    The labels are placed one after another, the most crowded phases first. Each label
    takes the Plotly ``textposition`` whose estimated box overlaps the fewest other
    labels, markers and tie lines and stays inside the triangle.

    Args:
        points: The stable phases to label.
        edges: Tie lines of the hull.

    Returns:
        One ``(textposition, text)`` pair per phase, in the order of ``points``.
    """
    scale = 1.0 / _TERNARY_SIDE_PX
    height = _LABEL_FONT_PX * 1.3 * scale
    gap = 0.012
    xy = [_ternary_xy(p.fractions) for p in points]
    segments = [(_ternary_xy(a.fractions), _ternary_xy(b.fractions)) for a, b in edges]
    degree = [sum(1 for a, b in edges if a is p or b is p) for p in points]
    result: List[Tuple[str, str]] = [("top center", "")] * len(points)
    placed: List[Tuple[float, float, float, float]] = []
    for index in sorted(range(len(points)), key=lambda i: -degree[i]):
        formula = points[index].entry.formula
        # Subscript digits are narrower than letters.
        chars = sum(0.7 if c.isdigit() or c == "." else 1.0 for c in formula)
        width = chars * _LABEL_FONT_PX * 0.6 * scale
        x, y = xy[index]
        others = [m for i, m in enumerate(xy) if i != index]
        best = min(
            _LABEL_POSITIONS,
            key=lambda pos: _label_penalty(
                _label_box(x, y, pos, width, height, gap), placed, others, segments, 6.0 * scale
            ),
        )
        placed.append(_label_box(x, y, best, width, height, gap))
        label = htmlify(formula)
        horizontal = best.split()[1]
        if horizontal == "right":
            label = "\u00a0\u00a0" + label
        elif horizontal == "left":
            label = label + "\u00a0\u00a0"
        result[index] = (best, label)
    return result


def _ternary(hull: CompoundHull, cutoff: float) -> Dict[str, Any]:
    """Triangular composition diagram."""
    unstable, above = _unstable(hull, cutoff)
    stable = hull.stable_points

    def abc(points: Sequence[Point]) -> Dict[str, List[float]]:
        return {
            "a": [float(p.fractions[0]) for p in points],
            "b": [float(p.fractions[1]) for p in points],
            "c": [float(p.fractions[2]) for p in points],
        }

    line_a: List[Optional[float]] = []
    line_b: List[Optional[float]] = []
    line_c: List[Optional[float]] = []
    for first, second in _edges(hull):
        line_a += [float(first.fractions[0]), float(second.fractions[0]), None]
        line_b += [float(first.fractions[1]), float(second.fractions[1]), None]
        line_c += [float(first.fractions[2]), float(second.fractions[2]), None]
    inner = [p for p in stable if p.fractions.max() < 1 - 1e-8]
    placements = _place_ternary_labels(inner, _edges(hull))
    data: List[Dict[str, Any]] = [
        {"type": "scatterternary", "mode": "lines", "a": line_a, "b": line_b, "c": line_c,
         "line": {"color": LINE_COLOR, "width": 1.5}, "hoverinfo": "none", "showlegend": False},
        {"type": "scatterternary", "mode": "markers", **abc(stable),
         **_marker_group("Stable", stable, np.zeros(len(stable)), hull, cutoff, True)},
        {"type": "scatterternary", "mode": "markers", **abc(unstable),
         **_marker_group("Above Hull", unstable, above, hull, cutoff, False)},
        {"type": "scatterternary", "mode": "text", "name": "Labels (stable)", **abc(inner),
         "text": [t for _, t in placements],
         "textposition": [pos for pos, _ in placements],
         "textfont": {"size": 13, "color": "#1f2937", "shadow": "0 0 3px #fff, 0 0 3px #fff"},
         "hoverinfo": "skip", "showlegend": False},
    ]
    labels = _terminal_labels(hull)
    axis = {"min": 0, "showgrid": True, "tickvals": [0.2, 0.4, 0.6, 0.8],
            "tickfont": {"size": 11, "color": "#555555"}, "gridcolor": "rgba(0,0,0,0.18)",
            "layer": "below traces"}
    layout = _base_layout()
    layout["margin"] = {"b": 80, "l": 60, "r": 60, "t": 70}
    layout["ternary"] = {
        "sum": 1,
        "aaxis": {**axis, "title": {"text": labels[0], "font": {"size": 18, "color": "#111827"}}},
        "baxis": {**axis, "title": {"text": labels[1], "font": {"size": 18, "color": "#111827"}}},
        "caxis": {**axis, "title": {"text": labels[2], "font": {"size": 18, "color": "#111827"}}},
    }
    return {"data": data, "layout": layout}


def _quaternary(hull: CompoundHull, cutoff: float) -> Dict[str, Any]:
    """Tetrahedron with the terminals at its corners."""
    unstable, above = _unstable(hull, cutoff)
    stable = hull.stable_points

    def xyz(points: Sequence[Point]) -> Dict[str, List[float]]:
        coords = np.array([p.fractions for p in points]).reshape(-1, 4) @ _TETRAHEDRON
        return {"x": coords[:, 0].tolist(), "y": coords[:, 1].tolist(), "z": coords[:, 2].tolist()}

    def segments(pairs: Sequence[Tuple[np.ndarray, np.ndarray]]) -> Dict[str, List[Optional[float]]]:
        out: Dict[str, List[Optional[float]]] = {"x": [], "y": [], "z": []}
        for first, second in pairs:
            for axis, key in enumerate(("x", "y", "z")):
                out[key] += [float(first[axis]), float(second[axis]), None]
        return out

    ties = [(p.fractions @ _TETRAHEDRON, q.fractions @ _TETRAHEDRON) for p, q in _edges(hull)]
    frame = [(_TETRAHEDRON[i], _TETRAHEDRON[j]) for i, j in combinations(range(4), 2)]
    inner = [p for p in stable if p.fractions.max() < 1 - 1e-8]
    labels = _terminal_labels(hull)
    data: List[Dict[str, Any]] = [
        {"type": "scatter3d", "mode": "lines", **segments(frame), "line": {"color": "#999999", "width": 2},
         "hoverinfo": "none", "showlegend": False},
        {"type": "scatter3d", "mode": "lines", **segments(ties), "line": {"color": LINE_COLOR, "width": 3},
         "hoverinfo": "none", "showlegend": False},
        {"type": "scatter3d", "mode": "markers", **xyz(stable),
         **_marker_group("Stable", stable, np.zeros(len(stable)), hull, cutoff, True, scale=0.5)},
        {"type": "scatter3d", "mode": "markers", **xyz(unstable),
         **_marker_group("Above Hull", unstable, above, hull, cutoff, False, scale=0.5)},
        {"type": "scatter3d", "mode": "text", "name": "Labels (stable)", **xyz(inner),
         "text": [htmlify(p.entry.formula) for p in inner], "textfont": {"size": 11},
         "hoverinfo": "skip", "showlegend": False},
        {"type": "scatter3d", "mode": "text", "name": "Terminals", "x": _TETRAHEDRON[:, 0].tolist(),
         "y": _TETRAHEDRON[:, 1].tolist(), "z": _TETRAHEDRON[:, 2].tolist(), "text": labels,
         "textfont": {"size": 16}, "hoverinfo": "skip", "showlegend": False},
    ]
    hidden = {"visible": False, "showgrid": False, "zeroline": False, "showbackground": False}
    layout = _base_layout()
    layout["margin"] = {"b": 0, "l": 0, "r": 0, "t": 30}
    layout["scene"] = {"xaxis": hidden, "yaxis": hidden, "zaxis": hidden, "aspectmode": "data",
                       "camera": {"eye": {"x": 1.4, "y": -1.4, "z": 0.9}}}
    return {"data": data, "layout": layout}
