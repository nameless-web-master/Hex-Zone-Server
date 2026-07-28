"""WebSocket realtime protocol: SUBSCRIBE, LOCATION_UPDATE (unit-level)."""
from starlette.testclient import TestClient

from app.main import app


def test_websocket_location_update_acks(monkeypatch):
    monkeypatch.setattr(
        "app.websocket.routes.verify_token",
        lambda token: {"sub": "42"},
    )

    class _Owner:
        id = 42

    class _SessionProxy:
        def close(self):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr("app.websocket.routes.session_maker", lambda: _SessionProxy())
    monkeypatch.setattr(
        "app.websocket.routes.owner_crud.get_owner",
        lambda db, owner_id: _Owner(),
    )
    monkeypatch.setattr(
        "app.websocket.routes.upsert_member_location",
        lambda db, owner_id, lat, lon: {"zones": ["zone-a"]},
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=fake") as ws:
            ws.send_json(
                {
                    "type": "LOCATION_UPDATE",
                    "latitude": 49.65,
                    "longitude": 23.85,
                }
            )
            ack = ws.receive_json()
            assert ack["type"] == "LOCATION_UPDATE_ACK"
            assert ack["data"]["zone_ids"] == ["zone-a"]


def test_websocket_subscribe_still_works(monkeypatch):
    monkeypatch.setattr(
        "app.websocket.routes.verify_token",
        lambda token: {"sub": "7"},
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=fake") as ws:
            ws.send_json({"type": "SUBSCRIBE", "zoneIds": ["zone-a"]})
            ack = ws.receive_json()
            assert ack["type"] == "SUBSCRIBED"
            assert ack["data"]["zoneIds"] == ["zone-a"]
