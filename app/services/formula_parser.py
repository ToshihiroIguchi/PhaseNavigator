"""Parsing and validation of user supplied chemical formulas."""
import re
from typing import List

from pymatgen.core.composition import Composition
from pymatgen.core.periodic_table import Element

# Characters accepted as separators between formulas: ASCII comma (U+002C),
# full-width comma (U+FF0C), ideographic comma (U+3001), semicolon (U+003B) and
# full-width semicolon (U+FF1B). Whitespace is deliberately NOT a separator
# because pymatgen reads "Fe2O3 Al2O3" as a single compound.
FORMULA_SEPARATOR_PATTERN = re.compile("[,，、;；]")


def split_formulas(text: str) -> List[str]:
    """
    Split a string of formulas into individual, trimmed formulas.

    Args:
        text: Raw user input such as "Fe2O3, Al2O3；SiO2".

    Returns:
        The non-empty formulas, in input order.
    """
    return [part.strip() for part in FORMULA_SEPARATOR_PATTERN.split(text) if part.strip()]


def parse_formula(formula: str) -> Composition:
    """
    Parse a single chemical formula into a pymatgen Composition.

    Args:
        formula: A formula such as "Fe2O3".

    Returns:
        The parsed composition.

    Raises:
        ValueError: If the formula contains whitespace, cannot be parsed, or
            contains something that is not a real chemical element.
    """
    formula = formula.strip()
    if not formula:
        raise ValueError("Empty chemical formula.")

    if re.search(r"\s", formula):
        raise ValueError(
            f"'{formula}' contains a space. Separate formulas with commas."
        )

    try:
        composition = Composition(formula)
    except Exception:
        raise ValueError(f"Invalid chemical formula: '{formula}'.")

    if composition.num_atoms == 0:
        raise ValueError(f"Invalid chemical formula: '{formula}'.")

    for species in composition:
        if not isinstance(species, Element):
            # pymatgen turns unknown symbols such as "Xx" into dummy species.
            symbol = re.sub(r"[0-9+\-]+$", "", str(species))
            raise ValueError(f"Unknown element '{symbol}' in formula '{formula}'.")

    return composition
