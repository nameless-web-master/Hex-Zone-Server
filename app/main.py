"""Main FastAPI application."""
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.database import init_db
from app.routers import owners, devices, zones, utils, messages
from app.routes.contract_routes import router as contract_router
from app.utils.api_response import error_response
from app.websocket.routes import router as websocket_router

logging.basicConfig(level=logging.INFO)

# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of the app."""
    # Startup
    print("Starting Zone Weaver backend...")
    try:
        init_db()
        print("Database initialized")
    except Exception as exc:
        logging.exception("Database initialization failed during startup: %s", exc)
        print("Continuing startup without DB initialization")
    yield
    # Shutdown
    print("Shutting down Zone Weaver backend...")


# Create FastAPI app
OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Service readiness and API discovery endpoints.",
    },
    {
        "name": "owners",
        "description": (
            "Registration, login, and owner profile management. Public GET "
            "/owners/registration-code issues administrator signup codes; POST /owners/register "
            "requires registration_code for administrator role. Exclusive accounts do not "
            "allow user-member registrations. Administrators can activate/deactivate linked users."
        ),
    },
    {
        "name": "zones",
        "description": (
            "Main Zone and optional Zone #2/#3 management. Includes Zone Matching, "
            "H3/grid, geofence, and related zone configuration payloads. Administrators can "
            "create only one Main Zone; users can create up to two zones. Zone listing follows "
            "role-aware visibility (admins see account zones, users see own zones plus admin main zone)."
        ),
    },
    {
        "name": "devices",
        "description": (
            "Device enrollment, presence heartbeat, and location updates. Device capacity is "
            "enforced by account tier per owner: private/exclusive/enhanced=1, private_plus=10, "
            "enhanced_plus=unlimited. Administrators can manage linked users' device active state."
        ),
    },
    {
        "name": "messages",
        "description": "Zone-scoped messaging for public and private communication.",
    },
    {
        "name": "utilities",
        "description": (
            "Helper endpoints for H3 conversion, QR registration flows, and public issuance of "
            "single-use administrator registration codes (GET /utils/registration-code). "
            "QR invitation generation is restricted to private-account administrators."
        ),
    },
    {
        "name": "contract",
        "description": (
            "Mobile app contract routes aligned to setup wizard flows (register, zone "
            "setup, schedule access, request access, and notifications)."
        ),
    },
]

app = FastAPI(
    title=settings.API_TITLE,
    description=(
        f"{settings.API_DESCRIPTION}\n\n"
        "This API supports setup wizard flows for administrator and user onboarding, "
        "including registration, account login, zone provisioning, access scheduling, "
        "QR-based onboarding, and zone messaging.\n\n"
        "Primary flow references:\n"
        "- Administrator registration: registration code + account + Main Zone + access-point setup. "
        "Fetch a code with GET /utils/registration-code (preferred) or GET /owners/registration-code, "
        "then send it as registrationCode on POST /register or registration_code on POST /owners/register. "
        "The tier code FREE is also accepted for administrators without calling GET (stateless).\n"
        "- User registration: account + optional Zone #2/#3 + schedule access + request access "
        "(no registration code required).\n"
        "- Login: email/username and password authentication."
    ),
    version=settings.API_VERSION,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled error processing request %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content=error_response("Internal server error"))


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    _ = request
    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message") or "Request failed")
        error_code = str(detail.get("error_code") or f"HTTP_{exc.status_code}")
        details = detail.get("details")
    else:
        message = str(detail) if detail else "Request failed"
        error_code = f"HTTP_{exc.status_code}"
        details = None

    payload = {
        "status": "error",
        "message": message,
        "error_code": error_code,
    }
    if details is not None:
        payload["details"] = details
    return JSONResponse(status_code=exc.status_code, content=payload)

# Include routers
app.include_router(owners.router)
app.include_router(devices.router)
app.include_router(zones.router)
app.include_router(messages.router)
app.include_router(utils.router)
app.include_router(contract_router)
app.include_router(websocket_router)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint."""
    return {
        "message": "Zone Weaver API",
        "version": settings.API_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
