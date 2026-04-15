"""In-memory websocket subscriptions with zone fanout."""
import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}
        self.user_zones: dict[str, set[str]] = defaultdict(set)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self.connections.pop(user_id, None)
        self.user_zones.pop(user_id, None)

    def subscribe(self, user_id: str, zone_ids: list[str]) -> None:
        self.user_zones[user_id] = set(zone_ids)

    async def broadcast_message(self, zone_id: str, payload: dict) -> None:
        message = {"type": "NEW_MESSAGE", "data": payload}
        text_data = json.dumps(message)
        for user_id, zones in self.user_zones.items():
            if zone_id in zones and user_id in self.connections:
                await self.connections[user_id].send_text(text_data)


ws_manager = WebSocketManager()
