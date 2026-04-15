"""WebSocket connection manager for zone subscriptions."""
from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    """Tracks active connections and zone subscriptions."""

    def __init__(self) -> None:
        self.connections: dict[int, WebSocket] = {}
        self.user_zones: dict[int, set[str]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        self.connections.pop(user_id, None)
        self.user_zones.pop(user_id, None)

    def subscribe(self, user_id: int, zone_id: str) -> None:
        self.user_zones[user_id].add(zone_id)

    async def broadcast_zone(self, zone_id: str, payload: dict) -> None:
        for user_id, zones in self.user_zones.items():
            if zone_id in zones and user_id in self.connections:
                await self.connections[user_id].send_json(payload)


manager = ConnectionManager()
