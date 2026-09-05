"""Twilio delivery callbacks for WhatsApp and Voice."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.recovery import OutboxMessage

router = APIRouter(tags=["twilio"])
log = get_logger("api.twilio")


async def _update_outbox(provider_id: str, status: str, db: AsyncSession):
    if not provider_id:
        return
    row = (await db.execute(select(OutboxMessage).where(OutboxMessage.provider_id == provider_id)
                            .order_by(OutboxMessage.created_at.desc()).limit(1))).scalar_one_or_none()
    if row:
        normalized = status.lower()
        if normalized in {"delivered", "read", "completed"}:
            row.status = "sent"
        elif normalized in {"failed", "undelivered", "busy", "no-answer", "canceled"}:
            row.status = "failed"
        await db.commit()


@router.post("/api/v1/webhooks/twilio/voice/status")
async def voice_status(db: AsyncSession = Depends(get_db),
                       CallSid: str = Form(default=""), CallStatus: str = Form(default="")):
    await _update_outbox(CallSid, CallStatus, db)
    log.info("twilio.voice_status", call_sid=CallSid[-10:] if CallSid else "", status=CallStatus)
    return {"ok": True}


@router.post("/api/v1/webhooks/twilio/whatsapp/status")
async def whatsapp_status(db: AsyncSession = Depends(get_db),
                          MessageSid: str = Form(default=""), MessageStatus: str = Form(default="")):
    await _update_outbox(MessageSid, MessageStatus, db)
    log.info("twilio.whatsapp_status", message_sid=MessageSid[-10:] if MessageSid else "", status=MessageStatus)
    return {"ok": True}
