import pytest
from pydantic import ValidationError

from app.models.requests import DiagramRequest, FormDiagramRequest
from app.services.formula_parser import parse_formula, split_formulas


@pytest.mark.parametrize(
    "text",
    [
        "Fe2O3, Al2O3, SiO2",
        "Fe2O3,Al2O3,SiO2",
        "Fe2O3，Al2O3，SiO2",  # full-width comma
        "Fe2O3、Al2O3、SiO2",  # ideographic comma
        "Fe2O3;Al2O3;SiO2",  # semicolon
        "Fe2O3；Al2O3；SiO2",  # full-width semicolon
        " Fe2O3 ,, Al2O3 , SiO2 , ",  # empty parts are dropped
    ],
)
def test_split_formulas_accepts_comma_like_separators(text):
    """All supported separators split into the same formulas."""
    assert split_formulas(text) == ["Fe2O3", "Al2O3", "SiO2"]


def test_split_formulas_does_not_split_on_space_or_hyphen():
    """Spaces and hyphens are not separators."""
    assert split_formulas("Fe2O3 Al2O3") == ["Fe2O3 Al2O3"]
    assert split_formulas("Fe2O3-Al2O3") == ["Fe2O3-Al2O3"]


def test_parse_formula_valid():
    """A normal formula parses into a composition."""
    assert parse_formula("Fe2O3").reduced_formula == "Fe2O3"
    assert parse_formula("(NH4)2SO4").num_atoms == 15


def test_parse_formula_rejects_space():
    """A space inside a formula is an error, not a silent merge."""
    with pytest.raises(ValueError, match="contains a space"):
        parse_formula("Fe2O3 Al2O3")


def test_parse_formula_rejects_unknown_element():
    """Dummy species such as Xx are reported by their symbol."""
    with pytest.raises(ValueError, match="Unknown element 'Xx'"):
        parse_formula("Xx2O3")


@pytest.mark.parametrize("formula", ["Fe2O3-Al2O3", "", "123"])
def test_parse_formula_rejects_garbage(formula):
    """Unparsable or empty formulas raise ValueError."""
    with pytest.raises(ValueError):
        parse_formula(formula)


def test_diagram_request_rejects_space_in_formula():
    """The API model rejects a formula that contains a space."""
    with pytest.raises(ValidationError, match="contains a space"):
        DiagramRequest(f=["Fe2O3 Al2O3", "SiO2"])


def test_diagram_request_rejects_unknown_element():
    """The API model rejects unknown elements with a readable message."""
    with pytest.raises(ValidationError, match="Unknown element 'Xx'"):
        DiagramRequest(f=["Xx2O3", "Al2O3"])


def test_form_request_accepts_fullwidth_separators():
    """The form model splits on full-width commas and ideographic commas."""
    form = FormDiagramRequest(formulas="Fe2O3，Al2O3、SiO2")
    assert form.to_diagram_request().formulas == ["Fe2O3", "Al2O3", "SiO2"]
