"""WebSocket routes."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.security import verify_token
from app.websocket.connection_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle realtime connections and zone subscriptions."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    payload = verify_token(token)
    user_id = int(payload["sub"])

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "SUBSCRIBE":
                zone_id = data.get("zone_id")
                if zone_id:
                    manager.subscribe(user_id, zone_id)
                    await websocket.send_json({"status": "success", "data": {"subscribed": zone_id}, "error": None})
            else:
                await websocket.send_json({"status": "error", "data": {}, "error": "Unsupported action"})
    except WebSocketDisconnect:
        manager.disconnect(user_id)
