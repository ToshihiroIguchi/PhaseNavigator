"""Compare the browser calculation core (phasecore) with the pymatgen server path."""
import json
from unittest.mock import Mock

import pytest
from pymatgen.analysis.phase_diagram import CompoundPhaseDiagram
from pymatgen.core import Composition
from pymatgen.entries.computed_entries import GibbsComputedStructureEntry

from app.services.formula_parser import parse_formula as pmg_parse_formula
from app.services.phase_analyzer import PhaseAnalyzer
from phasecore import generate_diagram
from phasecore.formula import parse_formula
from phasecore.gibbs import g_delta_sisso, reduced_mass
from tests.phasecore_data import make_dataset, make_entries


@pytest.fixture(scope="module")
def entries():
    """Synthetic pymatgen entries."""
    return make_entries()


@pytest.fixture(scope="module")
def dataset(entries):
    """The same entries as a phasecore dataset."""
    return make_dataset(entries)


def server_diagram(entries, formulas, temperature, cutoff=0.2):
    """Run the real server code path (PhaseAnalyzer + pymatgen) on the given entries."""
    elements = sorted({el.symbol for f in formulas for el in Composition(f).elements})
    pool = [e for e in entries if {el.symbol for el in e.composition.elements} <= set(elements)]
    if temperature > 0:
        pool = GibbsComputedStructureEntry.from_entries(pool, temp=temperature)
    client = Mock()
    client.get_elements_from_formulas.return_value = elements
    client.fetch_entries.return_value = (pool, 0)
    return PhaseAnalyzer(client).generate_phase_diagram(
        formulas=formulas, temperature=temperature, energy_cutoff=cutoff,
        functional="GGA_GGA_U", api_key="unused",
    )


def by_id(rows):
    """Index phase rows (dicts) by entry ID."""
    return {row["entry_id"]: row for row in rows}


CASES = [
    (["Fe", "Al", "O"], 0),
    (["Fe", "Al", "O"], 1000),
    (["Fe", "Al", "O"], 1050),
    (["Fe", "Al", "O"], 300),
    (["Fe2O3", "Al2O3"], 0),
    (["Fe2O3", "Al2O3"], 800),
    (["Fe2O3", "Al2O3", "FeO"], 0),
    (["Fe", "O"], 1273),
    (["C", "O"], 600),  # CO and CO2 are replaced by gas data
    (["H", "O"], 450),
    (["Fe", "Al", "O", "C"], 0),
    (["Fe", "Al", "O", "C"], 1100),
]


@pytest.mark.parametrize("formulas,temperature", CASES)
def test_phase_info_matches_pymatgen(entries, dataset, formulas, temperature):
    """Stable phases, energies, corrections and IDs agree with the pymatgen pipeline."""
    expected = by_id([row.model_dump() for row in server_diagram(entries, formulas, temperature).phase_info])
    actual = by_id(generate_diagram(dataset, formulas, temperature, 0.2, "GGA_GGA_U")["phase_info"])

    assert set(actual) == set(expected)
    for entry_id, want in expected.items():
        got = actual[entry_id]
        for key in ("formula", "composition", "temperature"):
            assert got[key] == want[key], (entry_id, key)
        for key in ("energy_per_atom", "total_energy", "formation_energy_per_atom", "correction", "num_atoms"):
            assert got[key] == pytest.approx(want[key], abs=2e-4), (entry_id, key)


@pytest.mark.parametrize("formulas,temperature", [(["Fe", "Al", "O"], 1000), (["Fe2O3", "Al2O3", "FeO"], 0)])
def test_energy_above_hull_matches_pymatgen(entries, dataset, formulas, temperature):
    """Energy above hull of every kept composition agrees with pymatgen."""
    from phasecore.gibbs import gibbs_entries
    from phasecore.hull import CompoundHull

    elements = sorted({el.symbol for f in formulas for el in Composition(f).elements})
    pool = [e for e in entries if {el.symbol for el in e.composition.elements} <= set(elements)]
    if temperature:
        pool = GibbsComputedStructureEntry.from_entries(pool, temp=temperature)
    pmg = CompoundPhaseDiagram(pool, [Composition(f) for f in formulas], normalize_terminal_compositions=True)
    expected = {str(e.original_entry.entry_id): pmg.get_e_above_hull(e, allow_negative=True) for e in pmg.all_entries}

    own_entries = dataset.select(elements)
    if temperature:
        own_entries = gibbs_entries(own_entries, temperature)
    hull = CompoundHull(own_entries, [parse_formula(f) for f in formulas], formulas)
    above = hull.energy_above_hull(hull.min_points)

    assert len(hull.min_points) > 5
    for point, value in zip(hull.min_points, above):
        assert value == pytest.approx(expected[point.entry.entry_id], abs=1e-6), point.entry.entry_id


def test_gas_entries_are_marked_experimental(dataset):
    """At finite temperature, entries with NIST-JANAF gas data are flagged like pymatgen does."""
    rows = generate_diagram(dataset, ["C", "O"], 600, 0.2, "GGA_GGA_U")["phase_info"]
    ids = {row["entry_id"] for row in rows}

    assert any(entry_id.endswith("(Experimental)") for entry_id in ids)


def test_reduced_mass_and_descriptor_match_pymatgen(entries):
    """The Bartel descriptor building blocks equal pymatgen's."""
    for entry in entries:
        if entry.composition.is_element:
            continue
        composition = {el.symbol: float(amount) for el, amount in entry.composition.items()}
        want_mass = GibbsComputedStructureEntry._reduced_mass(entry.structure)
        assert reduced_mass(composition) == pytest.approx(want_mass, rel=1e-12)
        volume = entry.structure.volume / len(entry.structure)
        want = GibbsComputedStructureEntry._g_delta_sisso(volume, want_mass, 1234)
        assert g_delta_sisso(volume, want_mass, 1234) == pytest.approx(want, rel=1e-12)


@pytest.mark.parametrize(
    "formula",
    ["Fe2O3", "Al2O3", "LiFePO4", "Ca(OH)2", "Mg3(PO4)2", "Fe0.5Al0.5O", "SiO2", "Na", "CH3COOH", "Ba[Ti(O)3]"],
)
def test_formula_parser_matches_pymatgen(formula):
    """Parsed amounts equal pymatgen's, including nested groups and repeated elements."""
    want = {el.symbol: amount for el, amount in pmg_parse_formula(formula).items()}
    got = parse_formula(formula)

    assert got == pytest.approx(want)


@pytest.mark.parametrize(
    "formula,message",
    [
        ("", "Empty chemical formula"),
        ("Fe2 O3", "contains a space"),
        ("Xx2O3", "Unknown element 'Xx'"),
        ("2Fe", "Invalid chemical formula"),
        ("Fe(O", "Invalid chemical formula"),
        ("FeO)", "Invalid chemical formula"),
        ("Fe0O", "Invalid chemical formula"),
    ],
)
def test_formula_parser_rejects_bad_input(formula, message):
    """Bad formulas give the same kind of message as the server."""
    with pytest.raises(ValueError, match=message):
        parse_formula(formula)


def test_response_is_json_serializable_with_expected_shape(dataset):
    """The result has the same top-level shape as the server response and is plain JSON."""
    result = generate_diagram(dataset, ["Fe2O3", "Al2O3"], 0, 0.2, "GGA_GGA_U")
    text = json.dumps(result, allow_nan=False)

    assert set(json.loads(text)) == {"plot", "phase_info", "metadata"}
    assert set(result["phase_info"][0]) == {
        "formula", "composition", "energy_per_atom", "total_energy", "formation_energy_per_atom",
        "correction", "entry_id", "temperature", "num_atoms",
    }
    assert result["metadata"]["num_phases"] == len(result["phase_info"])
    assert result["metadata"]["excluded_non_commercial"] == 0
    energies = [row["formation_energy_per_atom"] for row in result["phase_info"]]
    assert energies == sorted(energies)


@pytest.mark.parametrize(
    "formulas,expected_types",
    [
        (["Fe2O3", "Al2O3"], {"scatter"}),
        (["Fe", "Al", "O"], {"scatterternary"}),
        (["Fe", "Al", "O", "C"], {"scatter3d"}),
    ],
)
def test_figure_uses_the_right_trace_types(dataset, formulas, expected_types):
    """Binary, ternary and quaternary systems get 2D, ternary and 3D traces."""
    plot = generate_diagram(dataset, formulas, 0, 0.5, "GGA_GGA_U")["plot"]
    types = {trace["type"] for trace in plot["data"]}
    names = {trace.get("name") for trace in plot["data"]}

    assert types == expected_types
    assert {"Stable", "Above Hull"} <= names
    assert "Xf" not in json.dumps(plot)  # no leaked dummy species


def test_terminal_without_entry_is_reported(dataset):
    """A terminal formula missing from the data is named in the error."""
    with pytest.raises(ValueError, match="No entry found for 'Fe5O7'"):
        generate_diagram(dataset, ["Fe5O7", "Al2O3"], 0, 0.2, "GGA_GGA_U")


def test_linearly_dependent_terminals_are_rejected(dataset):
    """FeO, Fe2O3 and Fe3O4 cannot span a ternary diagram."""
    with pytest.raises(ValueError, match="linearly dependent"):
        generate_diagram(dataset, ["FeO", "Fe2O3", "Fe3O4"], 0, 0.2, "GGA_GGA_U")


@pytest.mark.parametrize(
    "formulas,temperature,cutoff,functional,message",
    [
        (["Fe2O3"], 0, 0.2, "GGA_GGA_U", "At least 2"),
        (["Fe", "O", "Al", "C", "H"], 0, 0.2, "GGA_GGA_U", "Maximum 4"),
        (["Fe", "O"], 100, 0.2, "GGA_GGA_U", "Temperature must be 0 K or between 300-2000 K"),
        (["Fe", "O"], 0, 5.0, "GGA_GGA_U", "Energy cutoff"),
        (["Fe", "O"], 0, 0.2, "PBE", "Unsupported functional"),
        (["Ac", "O"], 1000, 0.2, "GGA_GGA_U", "Finite-temperature data is not available for Ac"),
        (["Xe", "Kr"], 0, 0.2, "GGA_GGA_U", "No materials found"),
    ],
)
def test_invalid_requests_give_clear_errors(dataset, formulas, temperature, cutoff, functional, message):
    """Out-of-range or unsupported requests fail with a user-facing message."""
    with pytest.raises(ValueError, match=message):
        generate_diagram(dataset, formulas, temperature, cutoff, functional)


def test_ternary_figure_has_readable_axes_and_valid_label_positions(dataset):
    """Corner ticks are dropped and every label gets a known position and a legible font."""
    from phasecore.plotting import _LABEL_POSITIONS

    plot = generate_diagram(dataset, ["Fe", "Al", "O"], 0, 0.5, "GGA_GGA_U")["plot"]
    ternary = plot["layout"]["ternary"]
    for axis in ("aaxis", "baxis", "caxis"):
        assert 0 not in ternary[axis]["tickvals"] and 1 not in ternary[axis]["tickvals"]
        assert ternary[axis]["tickfont"]["size"] >= 11
    labels = next(t for t in plot["data"] if t.get("mode") == "text")
    assert labels["textfont"]["size"] >= 13
    assert len(labels["text"]) == len(labels["textposition"])
    assert set(labels["textposition"]) <= set(_LABEL_POSITIONS)


def test_ternary_labels_of_neighbouring_phases_do_not_overlap():
    """Phases that sit close together are labelled on different sides."""
    from types import SimpleNamespace

    from phasecore.plotting import _label_box, _place_ternary_labels, _ternary_xy

    def phase(formula, fractions):
        return SimpleNamespace(entry=SimpleNamespace(formula=formula), fractions=fractions)

    points = [
        phase("Ba2TiO4", (0.57, 0.29, 0.14)),
        phase("BaTiO3", (0.40, 0.40, 0.20)),
        phase("Ba6Y2Ti4O17", (0.52, 0.18, 0.30)),
        phase("BaTi2O5", (0.25, 0.60, 0.15)),
    ]
    placements = _place_ternary_labels(points, [])
    assert len(placements) == len(points)

    width_of = {p.entry.formula: len(p.entry.formula) * 13 * 0.6 / 600 for p in points}
    boxes = []
    for point, (position, _text) in zip(points, placements):
        x, y = _ternary_xy(point.fractions)
        boxes.append(_label_box(x, y, position, width_of[point.entry.formula], 13 * 1.3 / 600, 0.012))
    for i, first in enumerate(boxes):
        for second in boxes[i + 1:]:
            overlap_x = min(first[2], second[2]) - max(first[0], second[0])
            overlap_y = min(first[3], second[3]) - max(first[1], second[1])
            assert not (overlap_x > 0 and overlap_y > 0)
