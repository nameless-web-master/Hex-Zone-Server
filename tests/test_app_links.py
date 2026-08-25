"""App Links / Universal Links well-known files and HTTPS landing pages."""

from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import app_links


def test_asset_links_json(monkeypatch):
    monkeypatch.setattr(settings, "ANDROID_PACKAGE_NAME", "com.safezonepatrol.mobile")
    monkeypatch.setattr(
        settings,
        "ANDROID_SHA256_CERT_FINGERPRINTS",
        "AA:BB, cc:dd",
    )
    with TestClient(app) as client:
        res = client.get("/.well-known/assetlinks.json")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["target"]["package_name"] == "com.safezonepatrol.mobile"
    assert body[0]["target"]["sha256_cert_fingerprints"] == ["AA:BB", "CC:DD"]


def test_apple_app_site_association(monkeypatch):
    monkeypatch.setattr(settings, "APPLE_TEAM_ID", "ABCDE12345")
    monkeypatch.setattr(
        settings,
        "IOS_BUNDLE_ID",
        "com.neighbourhoodassistant.safe-zone-patrol",
    )
    with TestClient(app) as client:
        res = client.get("/.well-known/apple-app-site-association")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    detail = res.json()["applinks"]["details"][0]
    assert detail["appID"].startswith("ABCDE12345.")
    assert "/access*" in detail["paths"]
    assert "/join*" in detail["paths"]


def test_access_landing_opens_custom_scheme():
    with TestClient(app) as client:
        res = client.get("/access?gt=token1&zid=ZONE-1")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "safezonepatrol" in res.text
    assert "com.safezonepatrol.mobile" in res.text
    assert "intent://" in res.text


def test_join_landing_page():
    with TestClient(app) as client:
        res = client.get("/join?token=abc")
    assert res.status_code == 200
    assert "join" in res.text


def test_sha256_fingerprints_empty(monkeypatch):
    monkeypatch.setattr(settings, "ANDROID_SHA256_CERT_FINGERPRINTS", "")
    assert app_links.sha256_fingerprints() == []
