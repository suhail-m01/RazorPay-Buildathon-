"""Vonage Messages API webhook endpoints for WhatsApp Sandbox."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.recovery import OutboxMessage

router = APIRouter(tags=["vonage"])
log = get_logger("api.vonage")


async def _update_outbox(message_id: str, status: str, db: AsyncSession):
    if not message_id:
        return
    row = (await db.execute(select(OutboxMessage).where(OutboxMessage.provider_id == message_id)
                            .order_by(OutboxMessage.created_at.desc()).limit(1))).scalar_one_or_none()
    if row:
        normalized = (status or "").lower()
        if normalized in {"delivered", "read", "completed", "submitted"}:
            row.status = "sent"
        elif normalized in {"failed", "rejected", "undeliverable"}:
            row.status = "failed"
        await db.commit()


@router.post("/webhooks/vonage/whatsapp")
async def inbound(request: Request):
    payload = await request.json()
    log.info("vonage.whatsapp_inbound", message_type=payload.get("message_type", ""))
    return {"ok": True}


@router.post("/webhooks/vonage/whatsapp/status")
async def status(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    message_id = payload.get("message_uuid") or payload.get("messageId") or payload.get("message_id") or ""
    status_value = payload.get("status") or ""
    await _update_outbox(message_id, status_value, db)
    log.info("vonage.whatsapp_status", message_id=message_id[-12:] if message_id else "", status=status_value)
    return {"ok": True}


@router.api_route("/webhooks/vonage/voice/event", methods=["GET", "POST"])
async def voice_event(request: Request):
    if request.method == "GET":
        payload = dict(request.query_params)
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    status_value = payload.get("status", "")
    detail = payload.get("detail", "")
    call_uuid = payload.get("uuid", "")
    from_number = payload.get("from", "")
    to_number = payload.get("to", "")

    log.info(
        "vonage.voice_event",
        status=status_value,
        detail=detail,
        call_uuid=call_uuid[-12:] if call_uuid else "",
        from_number=from_number,
        to_number=to_number,
    )

    return {"ok": True}
