"""Main FastAPI application."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.database import init_db
from app.middleware.error_handlers import http_exception_handler, unhandled_exception_handler
from app.routes import auth, owners, devices, zones, messages, members, ws
from app.routers import utils
from app.utils.api_response import success_response

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
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
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

app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(owners.router)
app.include_router(devices.router)
app.include_router(zones.router)
app.include_router(messages.router)
app.include_router(members.router)
app.include_router(ws.router)
app.include_router(utils.router)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint."""
    return success_response({
        "message": "Zone Weaver API",
        "version": settings.API_VERSION,
        "docs": "/docs",
    })


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return success_response({"service": "healthy"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
