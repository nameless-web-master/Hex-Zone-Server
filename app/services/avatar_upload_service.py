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
MAX_CHAT_EDGE_PX = 1280
MAX_CHAT_DATA_URL_CHARS = 700_000
JPEG_QUALITY = 78
CHAT_JPEG_QUALITY = 72


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


def compress_to_jpeg_data_url(
    data: bytes,
    *,
    max_edge_px: int,
    quality: int,
    max_chars: int,
) -> str:
    """Resize/compress to a JPEG data URL suitable for DB + mobile Image."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail((max_edge_px, max_edge_px), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            compressed = out.getvalue()
    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode image. Try another photo.",
        ) from exc
    except Exception as exc:
        logger.warning("Image compress failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process image. Try another photo.",
        ) from exc

    data_url = "data:image/jpeg;base64," + base64.b64encode(compressed).decode("ascii")
    if len(data_url) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is still too large after compression. Crop tighter and try again.",
        )
    return data_url


def compress_avatar_to_data_url(data: bytes) -> str:
    """Resize/compress to a JPEG data URL suitable for DB + mobile Image."""
    return compress_to_jpeg_data_url(
        data,
        max_edge_px=MAX_AVATAR_EDGE_PX,
        quality=JPEG_QUALITY,
        max_chars=MAX_STORED_DATA_URL_CHARS,
    )


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


async def _persist_compressed_image(data_url: str, *, log_label: str) -> str:
    userhash = (settings.CATBOX_USERHASH or "").strip()
    if userhash:
        hosted = await _try_catbox_upload(_jpeg_bytes_from_data_url(data_url), userhash)
        if hosted:
            logger.info("%s uploaded to Catbox: %s", log_label, hosted)
            return hosted
        logger.info("Catbox upload skipped/failed for %s; storing compressed data URL", log_label)
    return data_url


async def upload_avatar_image(raw_image: str) -> str:
    """Return a persistable avatar URL (hosted HTTPS or data URL)."""
    data, _mime = parse_image_payload(raw_image)
    data_url = compress_avatar_to_data_url(data)
    return await _persist_compressed_image(data_url, log_label="Avatar")


async def upload_chat_image(raw_image: str) -> str:
    """Compress a chat photo and return a data URL.

    Chat photos are painted by React Native ``Image``, which often fails to load
    third-party hosts (same reason avatars are proxied). Keep a compressed data
    URL so inbox cards render without a separate media fetch.
    """
    data, _mime = parse_image_payload(raw_image)
    return compress_to_jpeg_data_url(
        data,
        max_edge_px=MAX_CHAT_EDGE_PX,
        quality=CHAT_JPEG_QUALITY,
        max_chars=MAX_CHAT_DATA_URL_CHARS,
    )


def owner_has_avatar(avatar_url: str | None) -> bool:
    return bool(avatar_url and str(avatar_url).strip())


def client_avatar_url(base_url: str, owner_id: int, avatar_url: str | None) -> str | None:
    """Never embed data: or third-party host URLs in JSON profiles.

    Mobile clients fetch GET /owners/{id}/avatar with auth and cache the bytes.
    Returning catbox/https directly often fails to paint in React Native Image.
    """
    raw = (avatar_url or "").strip()
    if not raw:
        return None
    base = (base_url or "").rstrip("/")
    return f"{base}/owners/{int(owner_id)}/avatar"


def avatar_bytes_and_media_type(avatar_url: str | None) -> tuple[bytes, str] | None:
    """Decode a stored avatar into raw bytes for HTTP image responses."""
    raw = (avatar_url or "").strip()
    if not raw:
        return None
    if raw.startswith("data:"):
        match = re.match(
            r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$",
            raw,
            flags=re.DOTALL,
        )
        if not match:
            return None
        mime = match.group(1).lower()
        try:
            data = base64.b64decode(match.group(2), validate=False)
        except Exception:
            return None
        if not data:
            return None
        return data, mime if mime != "image/jpg" else "image/jpeg"
    return None
