"""Helpers that turn framework validation errors into readable messages."""
from typing import Any, Dict, List

from .config import settings

_VALUE_ERROR_PREFIX = "Value error, "


def format_validation_errors(errors: List[Dict[str, Any]]) -> str:
    """
    Convert pydantic/FastAPI validation errors into one readable sentence.

    Args:
        errors: The list returned by ``RequestValidationError.errors()``.

    Returns:
        Messages joined by "; ", without internal details such as error types
        or location tuples.
    """
    messages: List[str] = []
    for error in errors:
        loc = error.get("loc") or ()
        field = str(loc[-1]) if loc else "request"
        error_type = error.get("type", "")
        msg = str(error.get("msg", "Invalid value"))

        if field == "f" and error_type == "too_short":
            text = f"At least {settings.min_formulas} chemical formulas are required"
        elif field == "f" and error_type == "too_long":
            text = f"Maximum {settings.max_formulas} formulas allowed"
        elif error_type == "missing":
            text = f"{field} is required"
        elif msg.startswith(_VALUE_ERROR_PREFIX):
            text = msg[len(_VALUE_ERROR_PREFIX):]
        else:
            text = f"{field}: {msg}"

        if text not in messages:
            messages.append(text)

    return "; ".join(messages) or "Invalid request"
