"""Android App Links + iOS Universal Links helpers (well-known files + QR landing)."""

from __future__ import annotations

import json
from html import escape

from app.core.config import settings


def sha256_fingerprints() -> list[str]:
    raw = (settings.ANDROID_SHA256_CERT_FINGERPRINTS or "").strip()
    if not raw:
        return []
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def asset_links_payload() -> list[dict]:
    fingerprints = sha256_fingerprints()
    return [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": settings.ANDROID_PACKAGE_NAME.strip()
                or "com.safezonepatrol.mobile",
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]


def apple_app_site_association_payload() -> dict:
    team = (settings.APPLE_TEAM_ID or "").strip()
    bundle = (settings.IOS_BUNDLE_ID or "").strip() or (
        "com.neighbourhoodassistant.safe-zone-patrol"
    )
    app_id = f"{team}.{bundle}" if team else bundle
    detail: dict = {
        "appID": app_id,
        "paths": ["/access*", "/join*"],
        "components": [
            {"/": "/access*"},
            {"/": "/join*"},
        ],
    }
    if team:
        detail["appIDs"] = [app_id]
    return {
        "applinks": {
            "apps": [],
            "details": [detail],
        }
    }


def _landing_html(kind: str) -> str:
    """HTML opened by camera/Chrome. Tries to hand off to the installed app."""
    scheme = (settings.APP_CUSTOM_SCHEME or "safezonepatrol").strip()
    package = (settings.ANDROID_PACKAGE_NAME or "com.safezonepatrol.mobile").strip()
    spa = (
        settings.GUEST_ACCESS_APP_BASE_URL or settings.PUBLIC_WEB_APP_URL or ""
    ).strip().rstrip("/")
    title = "Guest access" if kind == "access" else "Member invite"
    kind_js = json.dumps(kind)
    scheme_js = json.dumps(scheme)
    package_js = json.dumps(package)
    spa_js = json.dumps(spa)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Safe Zone Patrol — {escape(title)}</title>
    <style>
      body {{
        font-family: system-ui, sans-serif;
        background: #f4f7fb;
        color: #0f2c5c;
        margin: 0;
        padding: 32px 20px;
      }}
      .card {{
        max-width: 420px;
        margin: 0 auto;
        background: #fff;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(15, 44, 92, 0.08);
      }}
      h1 {{ font-size: 20px; margin: 0 0 8px; }}
      p {{ color: #5b6b86; line-height: 1.45; }}
      a, button {{
        display: block;
        width: 100%;
        box-sizing: border-box;
        text-align: center;
        margin-top: 12px;
        padding: 12px 16px;
        border-radius: 10px;
        font-weight: 700;
        text-decoration: none;
        border: 0;
        cursor: pointer;
      }}
      .primary {{ background: #2f80ed; color: #fff; }}
      .secondary {{ background: #e8eef8; color: #0f2c5c; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{escape(title)}</h1>
      <p id="status">Opening Safe Zone Patrol…</p>
      <button class="primary" id="open" type="button">Open in app</button>
      <a class="secondary" id="web" href="#" hidden>Continue in browser</a>
    </div>
    <script>
      var KIND = {kind_js};
      var SCHEME = {scheme_js};
      var PKG = {package_js};
      var SPA = {spa_js};
      var qs = window.location.search || "";
      var custom = SCHEME + ":///" + KIND + qs;
      var intent = "intent://" + KIND + qs +
        "#Intent;scheme=" + SCHEME + ";package=" + PKG + ";end";
      var spaUrl = SPA ? (SPA + "/" + KIND + qs) : "";
      var web = document.getElementById("web");
      if (spaUrl && spaUrl.indexOf(window.location.origin) !== 0) {{
        web.hidden = false;
        web.href = spaUrl;
      }}
      function openApp() {{
        var ua = navigator.userAgent || "";
        window.location.href = /android/i.test(ua) ? intent : custom;
      }}
      document.getElementById("open").addEventListener("click", openApp);
      openApp();
      setTimeout(function () {{
        document.getElementById("status").textContent =
          "If the app did not open, tap Open in app. If it is not installed, continue in the browser.";
      }}, 1200);
    </script>
  </body>
</html>
"""


def access_landing_html() -> str:
    return _landing_html("access")


def join_landing_html() -> str:
    return _landing_html("join")
