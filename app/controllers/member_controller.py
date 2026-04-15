"""Member controller."""
from app.services import member_service


def list_members(db):
    return member_service.list_members(db)


def update_location(db, owner_id: int, latitude: float, longitude: float):
    return member_service.update_member_location(db, owner_id, latitude, longitude)
