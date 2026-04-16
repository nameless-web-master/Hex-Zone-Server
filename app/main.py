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
    init_db()
    print("Database initialized")
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
        "description": "Registration, login, and owner profile management.",
    },
    {
        "name": "zones",
        "description": (
            "Main Zone and optional Zone #2/#3 management. Includes Zone Matching, "
            "H3/grid, geofence, and related zone configuration payloads."
        ),
    },
    {
        "name": "devices",
        "description": "Device enrollment, presence heartbeat, and location updates.",
    },
    {
        "name": "messages",
        "description": "Zone-scoped messaging for public and private communication.",
    },
    {
        "name": "utilities",
        "description": "Helper endpoints for H3 conversion and QR registration flows.",
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
        "- Administrator registration: reg-code + account + Main Zone + access-point setup.\n"
        "- User registration: account + optional Zone #2/#3 + schedule access + request access.\n"
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
    message = str(exc.detail) if exc.detail else "Request failed"
    return JSONResponse(status_code=exc.status_code, content=error_response(message))

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
