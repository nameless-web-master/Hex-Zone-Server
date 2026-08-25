"""Public HTTPS App Link / Universal Link endpoints."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.services import app_links

router = APIRouter(tags=["app-links"])


@router.get("/.well-known/assetlinks.json")
async def android_asset_links() -> JSONResponse:
    return JSONResponse(
        content=app_links.asset_links_payload(),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/.well-known/apple-app-site-association")
async def apple_app_site_association() -> JSONResponse:
    return JSONResponse(
        content=app_links.apple_app_site_association_payload(),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/access", response_class=HTMLResponse)
async def access_app_link_landing() -> HTMLResponse:
    return HTMLResponse(content=app_links.access_landing_html())


@router.get("/join", response_class=HTMLResponse)
async def join_app_link_landing() -> HTMLResponse:
    return HTMLResponse(content=app_links.join_landing_html())
