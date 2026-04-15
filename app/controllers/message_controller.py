"""Message controller."""
from app.services import message_service


def create_message(db, owner_id: int, payload):
    return message_service.create_message(db, owner_id, payload)
