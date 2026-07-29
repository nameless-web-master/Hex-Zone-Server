"""Prepare and persist profile avatars.

Catbox (and similar anonymous hosts) often block datacenter IPs with
``412 Invalid uploader``, which is why production uploads failed with 502.
Primary path: validate + compress with Pillow and store a data URL on the
owner row. Optional Catbox upload runs only when ``CATBOX_USERHASH`` is set
and succeeds; otherwise we keep the local data URL.
"""
from __future__ import annotations

import base64
import io
import logging
import re
from typing import Tuple

import httpx
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings

logger = logging.getLogger(__name__)

CATBOX_UPLOAD_URL = "https://catbox.moe/user/api.php"
MAX_INPUT_BYTES = 2_500_000
MAX_STORED_DATA_URL_CHARS = 320_000
MAX_AVATAR_EDGE_PX = 512
JPEG_QUALITY = 78


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
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image encoding",
        ) from exc

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is empty",
        )
    if len(data) > MAX_INPUT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large (max about 2.5 MB)",
        )
    return data, "image/jpeg" if mime == "image/jpg" else mime


def compress_avatar_to_data_url(data: bytes) -> str:
    """Resize/compress to a JPEG data URL suitable for DB + mobile Image."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail(
                (MAX_AVATAR_EDGE_PX, MAX_AVATAR_EDGE_PX),
                Image.Resampling.LANCZOS,
            )
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            compressed = out.getvalue()
    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode image. Try another photo.",
        ) from exc
    except Exception as exc:
        logger.warning("Avatar compress failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process image. Try another photo.",
        ) from exc

    data_url = "data:image/jpeg;base64," + base64.b64encode(compressed).decode("ascii")
    if len(data_url) > MAX_STORED_DATA_URL_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is still too large after compression. Crop tighter and try again.",
        )
    return data_url


async def _try_catbox_upload(jpeg_bytes: bytes, userhash: str) -> str | None:
    """Best-effort Catbox upload. Returns HTTPS URL or None on failure."""
    form: dict[str, str] = {"reqtype": "fileupload", "userhash": userhash}
    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            headers={"User-Agent": "SafeZonePatrol/1.0 (+avatar-upload)"},
            follow_redirects=True,
        ) as client:
            response = await client.post(
                CATBOX_UPLOAD_URL,
                data=form,
                files={"fileToUpload": ("avatar.jpg", jpeg_bytes, "image/jpeg")},
            )
    except httpx.HTTPError as exc:
        logger.warning("Catbox unreachable: %s", exc)
        return None

    body = (response.text or "").strip()
    if response.status_code >= 400:
        logger.warning(
            "Catbox rejected upload status=%s body=%s",
            response.status_code,
            body[:200],
        )
        return None

    # Accept http(s) and normalize to https for files.catbox.moe
    if body.startswith("http://"):
        body = "https://" + body[len("http://") :]
    if not body.startswith("https://"):
        logger.warning("Catbox returned non-URL body: %s", body[:200])
        return None
    return body


def _jpeg_bytes_from_data_url(data_url: str) -> bytes:
    raw = data_url.split(",", 1)[1]
    return base64.b64decode(raw)


async def upload_avatar_image(raw_image: str) -> str:
    """Return a persistable avatar URL (hosted HTTPS or data URL)."""
    data, _mime = parse_image_payload(raw_image)
    data_url = compress_avatar_to_data_url(data)

    userhash = (settings.CATBOX_USERHASH or "").strip()
    if userhash:
        hosted = await _try_catbox_upload(_jpeg_bytes_from_data_url(data_url), userhash)
        if hosted:
            logger.info("Avatar uploaded to Catbox: %s", hosted)
            return hosted
        logger.info("Catbox upload skipped/failed; storing compressed data URL")

    return data_url
