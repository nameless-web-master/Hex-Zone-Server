"""Outbound smart-home webhook delivery for geo-propagated alarms/alerts.

When an owner configures ``owners.sn_webhook``, Hex Zone POSTs each delivered
geo message to that URL so a hub can sound/show the alarm without polling.
Failures never fail the originating request.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.message_types import is_pushable_geo_type
from app.models import Owner

logger = logging.getLogger(__name__)


def _webhook_timeout_seconds() -> float:
    return max(1.0, float(getattr(settings, "SMART_HOME_WEBHOOK_TIMEOUT_SECONDS", 5)))


def is_valid_webhook_url(url: str) -> bool:
    """Accept only absolute http(s) URLs."""
    raw = (url or "").strip()
    if not raw or len(raw) > 2048:
        return False
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    return True


def build_smart_home_webhook_payload(
    alarm_payload: dict[str, Any],
    *,
    recipient_owner_id: int,
    network_id: str | None = None,
) -> dict[str, Any]:
    """Stable JSON body hubs can parse for sirens / notifications."""
    metadata = alarm_payload.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    hid = str(metadata_dict.get("hid") or "").strip()
    return {
        "event": "SMART_HOME_ALARM",
        "id": alarm_payload.get("id"),
        "type": str(alarm_payload.get("type") or "").strip().upper(),
        "category": str(alarm_payload.get("category") or ""),
        "scope": str(alarm_payload.get("scope") or ""),
        "priority": str(alarm_payload.get("priority") or ""),
        "text": str(alarm_payload.get("text") or ""),
        "sender_id": alarm_payload.get("sender_id"),
        "zone_id": alarm_payload.get("zone_id"),
        "network_id": (network_id or "").strip(),
        "recipient_owner_id": recipient_owner_id,
        "hid": hid,
        "created_at": alarm_payload.get("created_at"),
        "response_tracking_enabled": bool(
            alarm_payload.get("response_tracking_enabled")
        ),
        "metadata": metadata_dict,
    }


async def _post_webhook(
    client: httpx.AsyncClient,
    *,
    url: str,
    body: dict[str, Any],
) -> bool:
    try:
        response = await client.post(url, json=body)
        if response.status_code >= 400:
            logger.warning(
                "Smart-home webhook HTTP %s for %s (type=%s id=%s)",
                response.status_code,
                url,
                body.get("type"),
                body.get("id"),
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning(
            "Smart-home webhook failed for %s (type=%s id=%s): %s",
            url,
            body.get("type"),
            body.get("id"),
            exc,
        )
        return False


async def send_smart_home_webhooks(
    db: Session,
    owner_ids: list[int],
    alarm_payload: dict[str, Any],
) -> dict[str, Any]:
    """POST the alarm to each recipient owner's configured webhook URL.

    Returns counts for response diagnostics. Never raises.
    """
    msg_type = str(alarm_payload.get("type") or "")
    if not is_pushable_geo_type(msg_type):
        return {"webhook_sent": 0, "webhook_failed": 0, "webhook_skipped": True}

    unique_ids = sorted({int(oid) for oid in owner_ids if isinstance(oid, int)})
    if not unique_ids:
        return {"webhook_sent": 0, "webhook_failed": 0, "webhook_no_targets": True}

    owners = (
        db.query(Owner)
        .filter(Owner.id.in_(unique_ids), Owner.active.is_(True))
        .all()
    )
    targets: list[tuple[Owner, str]] = []
    for owner in owners:
        url = str(getattr(owner, "sn_webhook", "") or "").strip()
        if not url:
            continue
        if not is_valid_webhook_url(url):
            logger.warning(
                "Ignoring invalid smart-home webhook for owner %s: %s",
                owner.id,
                url[:80],
            )
            continue
        targets.append((owner, url))

    if not targets:
        return {
            "webhook_sent": 0,
            "webhook_failed": 0,
            "webhook_no_urls": True,
        }

    sent = 0
    failed = 0
    timeout = _webhook_timeout_seconds()
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "HexZone-SmartHomeWebhook/1.0",
            "X-Hex-Zone-Event": "SMART_HOME_ALARM",
        },
    ) as client:
        for owner, url in targets:
            body = build_smart_home_webhook_payload(
                alarm_payload,
                recipient_owner_id=owner.id,
                network_id=str(owner.zone_id or ""),
            )
            ok = await _post_webhook(client, url=url, body=body)
            if ok:
                sent += 1
            else:
                failed += 1

    logger.info(
        "Smart-home webhook type=%s targets=%d sent=%d failed=%d",
        msg_type,
        len(targets),
        sent,
        failed,
    )
    return {
        "webhook_sent": sent,
        "webhook_failed": failed,
        "webhook_targets": len(targets),
    }
