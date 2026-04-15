"""Zone controller."""
from app.services import zone_service


def create_zone(db, owner_id: int, payload):
    return zone_service.create_zone(db, owner_id, payload)


def update_zone(db, owner_id: int, zone_id: str, payload):
    return zone_service.update_zone(db, owner_id, zone_id, payload)
