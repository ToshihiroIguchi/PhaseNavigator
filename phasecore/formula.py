"""Chemical formula parsing without pymatgen."""
from __future__ import annotations

import re
from typing import Dict, List

from .tables import ATOMIC_MASSES

_TOKEN = re.compile(r"([A-Z][a-z]*)|(\d+(?:\.\d+)?|\.\d+)|([(\[])|([)\]])")


def parse_formula(formula: str) -> Dict[str, float]:
    """
    Parse a chemical formula into element amounts.

    Supports element symbols, integer or decimal amounts and nested parentheses or
    square brackets, e.g. ``"Ca(OH)2"``. Repeated elements are summed and keep the
    position of their first appearance.

    Args:
        formula: A formula such as ``"Fe2O3"``.

    Returns:
        Ordered mapping from element symbol to amount.

    Raises:
        ValueError: If the formula is empty, contains whitespace, cannot be parsed,
            or contains something that is not a chemical element.
    """
    text = formula.strip()
    if not text:
        raise ValueError("Empty chemical formula.")
    if re.search(r"\s", text):
        raise ValueError(f"'{text}' contains a space. Separate formulas with commas.")

    invalid = ValueError(f"Invalid chemical formula: '{text}'.")
    # Each open group is a list of [symbol, amount] pairs; pairs are mutated in place
    # when a multiplier follows an element or a closed group.
    stack: List[List[List]] = [[]]
    last_item: List[List] = []  # pairs a following number applies to
    position = 0

    while position < len(text):
        match = _TOKEN.match(text, position)
        if not match:
            raise invalid
        position = match.end()
        symbol, number, opener, closer = match.groups()

        if symbol:
            if symbol not in ATOMIC_MASSES:
                raise ValueError(f"Unknown element '{symbol}' in formula '{text}'.")
            pair = [symbol, 1.0]
            stack[-1].append(pair)
            last_item = [pair]
        elif number:
            factor = float(number)
            if not last_item or factor <= 0:
                raise invalid
            for pair in last_item:
                pair[1] *= factor
            last_item = []
        elif opener:
            stack.append([])
            last_item = []
        else:
            if len(stack) == 1:
                raise invalid
            group = stack.pop()
            stack[-1].extend(group)
            last_item = group

    if len(stack) != 1 or not stack[0]:
        raise invalid

    amounts: Dict[str, float] = {}
    for symbol, amount in stack[0]:
        amounts[symbol] = amounts.get(symbol, 0.0) + amount
    return amounts
