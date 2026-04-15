"""Global API error handlers."""
import logging
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app.utils.api_response import error_response


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException into standard response envelope."""
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return error_response(detail, exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert unexpected exceptions into standard response envelope."""
    logging.exception("Unhandled error processing request %s %s", request.method, request.url)
    return error_response("Internal server error", 500)
