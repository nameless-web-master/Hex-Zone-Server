"""Controller layer for contract APIs."""
from app.services import auth_service, member_service, message_service, zone_service


def login(db, payload: dict) -> dict:
    return auth_service.login_user(db, payload["email"], payload["password"])


def register(db, payload: dict) -> dict:
    return auth_service.register_user(db, payload)


def create_zone(db, owner, payload: dict) -> dict:
    return zone_service.create_zone(db, owner, payload)


def list_zones(db, owner) -> list[dict]:
    return zone_service.list_zones(db, owner)


def update_zone(db, owner, zone_id: str, payload: dict) -> dict:
    return zone_service.update_zone(db, owner, zone_id, payload)


def delete_zone(db, owner, zone_id: str) -> None:
    zone_service.delete_zone(db, owner, zone_id)


def create_message(db, owner, payload: dict) -> dict:
    return message_service.create_zone_message(db, owner.id, payload)


def get_new_messages(db, since: str) -> list[dict]:
    return message_service.list_new_messages(db, since)


def update_location(db, owner, latitude: float, longitude: float) -> dict:
    return member_service.upsert_member_location(db, owner.id, latitude, longitude)


def get_members(db, owner) -> list[dict]:
    return member_service.list_members(db, owner)


def register_push_token(db, owner, token: str, platform: str) -> dict:
    return member_service.upsert_push_token(db, owner.id, token, platform)
