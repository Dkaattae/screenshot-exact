import json
from typing import Any

from app.errors import validation_error


def parse_measurements(raw: str | None) -> dict[str, float | None]:
    """Multipart forms send measurements as a JSON string: {name: number | null}."""
    if not raw:
        return {}
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise validation_error("Measurements must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise validation_error("Measurements must be an object of name to number.")
    result: dict[str, float | None] = {}
    for name, value in data.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise validation_error(f"Measurement {name} must be a number or null.")
        if value is not None and value <= 0:
            raise validation_error(f"Measurement {name} must be greater than 0.")
        result[str(name)] = None if value is None else float(value)
    return result
