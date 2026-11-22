"""Phase diagram calculation core for the static (browser) edition.

Depends only on the standard library, numpy and scipy so that it runs both in
CPython (tests, data tooling) and in the browser through Pyodide.
"""
from .diagram import FUNCTIONAL_THERMO_TYPES, generate_diagram
from .entries import Dataset, Entry

__all__ = ["Dataset", "Entry", "FUNCTIONAL_THERMO_TYPES", "generate_diagram"]
