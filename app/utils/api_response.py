"""API response envelope helpers."""
from fastapi.responses import JSONResponse


def success_response(data, status_code: int = 200) -> JSONResponse:
    """Return a success response using the API envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"status": "success", "data": data, "error": None},
    )


def error_response(message: str, status_code: int) -> JSONResponse:
    """Return an error response using the API envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "data": {}, "error": message},
    )
