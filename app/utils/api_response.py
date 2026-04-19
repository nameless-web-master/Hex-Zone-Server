"""Standard API response helpers."""
from typing import Any


def success_response(data: Any) -> dict[str, Any]:
    return {"status": "success", "data": data, "error": None}


def error_response(message: str, data: Any | None = None) -> dict[str, Any]:
    return {"status": "error", "data": data or {}, "error": {"message": message}}
