"""Websocket endpoint for realtime zone subscriptions."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import HTTPException

from app.core.security import verify_token
from app.websocket.manager import ws_manager

router = APIRouter()


async def _zone_websocket_session(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return
    try:
        payload = verify_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid token")
        return
    user_id = str(payload.get("sub"))
    if not user_id or user_id == "None":
        await websocket.close(code=1008, reason="Invalid token")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "SUBSCRIBE":
                zone_ids = data.get("zoneIds", [])
                if isinstance(zone_ids, list):
                    ws_manager.subscribe(user_id, [str(item) for item in zone_ids])
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)


@router.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    await _zone_websocket_session(websocket)


@router.websocket("/ws/messages")
async def websocket_messages_alias(websocket: WebSocket):
    """Compatibility alias for clients expecting /ws/messages (same handshake as /ws)."""
    await _zone_websocket_session(websocket)
