"""Entry points called from JavaScript in the browser (Pyodide).

JavaScript hands over the text of a dataset file once per functional and then asks for
diagrams. Errors that the user can act on are returned as data instead of raised, so
the page never has to parse a Python traceback.
"""
from __future__ import annotations

import json
from typing import Dict

from .diagram import generate_diagram
from .entries import Dataset

_DATASETS: Dict[str, Dataset] = {}


def load_dataset(functional: str, text: str) -> int:
    """
    Parse and keep a dataset for later requests.

    Args:
        functional: UI functional name the dataset belongs to.
        text: JSON text of the dataset file.

    Returns:
        Number of entries loaded.

    Raises:
        ValueError: If the file layout is not supported.
    """
    _DATASETS[functional] = Dataset.from_json(text)
    return len(_DATASETS[functional])


def has_dataset(functional: str) -> bool:
    """
    Tell whether a dataset has been loaded.

    Args:
        functional: UI functional name.

    Returns:
        True if ``load_dataset`` has been called for it.
    """
    return functional in _DATASETS


def run(request_json: str) -> str:
    """
    Build a diagram for a request.

    Args:
        request_json: JSON object with ``formulas``, ``temperature``, ``e_cut`` and
            ``functional``.

    Returns:
        JSON text: ``{"ok": true, "result": {...}}`` or ``{"ok": false, "error": "..."}``
        when the input or the bundled data cannot satisfy the request.
    """
    request = json.loads(request_json)
    functional = request["functional"]
    if functional not in _DATASETS:
        return json.dumps({"ok": False, "error": f"No data is loaded for {functional}."})
    try:
        result = generate_diagram(
            _DATASETS[functional],
            request["formulas"],
            int(request["temperature"]),
            float(request["e_cut"]),
            functional,
        )
    except ValueError as error:
        return json.dumps({"ok": False, "error": str(error)})
    return json.dumps({"ok": True, "result": result}, allow_nan=False)
