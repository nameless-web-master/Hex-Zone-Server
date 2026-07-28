"""Upload profile avatars to a third-party image host."""
from __future__ import annotations

import base64
import logging
import re
from typing import Tuple

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Free anonymous host (no API key). Returns a plain-text public HTTPS URL.
CATBOX_UPLOAD_URL = "https://catbox.moe/user/api.php"
MAX_AVATAR_BYTES = 2_500_000  # ~2.5 MB decoded


def parse_image_payload(raw: str) -> Tuple[bytes, str]:
    """Accept a data URL or raw base64 string; return (bytes, mime)."""
    text = (raw or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image data is required",
        )

    mime = "image/jpeg"
    b64 = text
    match = re.match(
        r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$",
        text,
        flags=re.DOTALL,
    )
    if match:
        mime = match.group(1).lower()
        b64 = match.group(2)

    if mime not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type. Use JPEG, PNG, WebP, or GIF.",
        )

    try:
        data = base64.b64decode(b64, validate=False)
    except Exception as exc:  # pragma: no cover - invalid base64
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image encoding",
        ) from exc

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is empty",
        )
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large (max about 2.5 MB)",
        )
    return data, "image/jpeg" if mime == "image/jpg" else mime


def _extension_for_mime(mime: str) -> str:
    if mime == "image/png":
        return "png"
    if mime == "image/webp":
        return "webp"
    if mime == "image/gif":
        return "gif"
    return "jpg"


async def upload_avatar_image(raw_image: str) -> str:
    """Upload image bytes to Catbox and return the public URL."""
    data, mime = parse_image_payload(raw_image)
    filename = f"avatar.{_extension_for_mime(mime)}"

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                CATBOX_UPLOAD_URL,
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (filename, data, mime)},
            )
    except httpx.HTTPError as exc:
        logger.warning("Avatar host unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach image upload service",
        ) from exc

    if response.status_code >= 400:
        logger.warning(
            "Avatar host error status=%s body=%s",
            response.status_code,
            (response.text or "")[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image upload service rejected the file",
        )

    url = (response.text or "").strip()
    if not url.startswith("https://"):
        logger.warning("Avatar host returned unexpected body: %s", url[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image upload service returned an invalid URL",
        )
    return url
