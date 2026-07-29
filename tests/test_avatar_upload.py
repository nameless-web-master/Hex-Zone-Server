"""Avatar upload: compress locally; Catbox is optional."""
import base64
import io

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.avatar_upload_service import (
    compress_avatar_to_data_url,
    parse_image_payload,
    upload_avatar_image,
)


def _tiny_jpeg_bytes(size: int = 64) -> bytes:
    img = Image.new("RGB", (size, size), color=(40, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_parse_data_url_jpeg():
    raw = _tiny_jpeg_bytes()
    data_url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    data, mime = parse_image_payload(data_url)
    assert mime == "image/jpeg"
    assert data[:2] == b"\xff\xd8"


def test_compress_produces_smaller_data_url():
    raw = _tiny_jpeg_bytes(800)
    data_url = compress_avatar_to_data_url(raw)
    assert data_url.startswith("data:image/jpeg;base64,")
    decoded = base64.b64decode(data_url.split(",", 1)[1])
    assert len(decoded) < len(raw)


def test_parse_rejects_empty():
    with pytest.raises(HTTPException) as exc:
        parse_image_payload("")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_avatar_image_stores_data_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.avatar_upload_service.settings.CATBOX_USERHASH",
        "",
        raising=False,
    )
    raw = _tiny_jpeg_bytes(120)
    payload = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    result = await upload_avatar_image(payload)
    assert result.startswith("data:image/jpeg;base64,")
