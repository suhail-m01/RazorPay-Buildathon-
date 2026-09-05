"""Inbound WhatsApp webhook (Twilio). A customer's WhatsApp reply runs through the
SAME promise/reply engine as the portal and email, and the agent's answer is sent
straight back into the chat via TwiML. Registered in Twilio as:
  https://<host>/webhook/whatsapp      (also served at /api/v1/webhooks/whatsapp)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.track import submit_reply
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.ratelimit import rate_limit
from app.models.base import Customer
from app.models.recovery import RecoveryCase

log = get_logger("api.whatsapp_inbound")
router = APIRouter(tags=["whatsapp"])

TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>{text}</Message></Response>'


def _twiml(text: str) -> Response:
    return Response(TWIML.format(text=(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:600]),
                    media_type="application/xml")


async def handle(request: Request, From: str, Body: str, db: AsyncSession) -> Response:
    phone = From.replace("whatsapp:", "").strip()
    if not await rate_limit(f"wa-in:{phone}", 20, 60):
        return _twiml("Too many messages — please wait a minute.")

    customer = (await db.execute(select(Customer).where(Customer.phone == phone))).scalars().first()
    if not customer:
        log.info("whatsapp_in.unknown_sender", to=phone[:6] + "***")
        return _twiml("Thanks for your message! We couldn't find an account for this number. If you have a payment due, use the link we emailed you.")
    if customer.opted_out:
        return _twiml("You have opted out of all contact. We will not message you again.")

    case = (await db.execute(select(RecoveryCase).where(RecoveryCase.customer_id == customer.id,
                                                       RecoveryCase.status.in_(("open", "escalated")))
                             .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalars().first()
    if not case:
        # No open case — but there may be pending payment requests; quote them with a live link.
        from app.models.base import Invoice
        from app.models.settings import load_creds

        unpaid = (await db.execute(select(Invoice).where(Invoice.customer_id == customer.id,
                                                        Invoice.status.in_(("pending", "failed")))
                                   .order_by(Invoice.created_at.desc()).limit(5))).scalars().all()
        if not unpaid:
            return _twiml(f"Hi {customer.name.split(' ')[0]} — you have no pending payments with us. Have a great day!")
        total = sum(i.amount_paise for i in unpaid)
        creds = await load_creds(db, customer.merchant_id)
        from app.integrations import razorpay_client

        link = await razorpay_client.create_payment_link(total, f"rp-wa-{customer.id[-6:]}", base_url=request, creds=creds)
        return _twiml(f"Hi {customer.name.split(' ')[0]} — you have {len(unpaid)} pending payment(s) totalling ₹{total / 100:,.0f}. Pay securely: {link['url']}")

    base = str(request.base_url).replace(":8000", ":3000").rstrip("/")
    outcome = await submit_reply(db, case, (Body or "").strip()[:800], f"customer:whatsapp:{customer.id}", base, source="whatsapp")
    log.info("whatsapp_in.replied", case=case.seq, intent=outcome.get("intent"), accepted=outcome.get("accepted"))
    return _twiml(outcome.get("reply_body") or outcome.get("reply_subject") or "Noted — thank you!")


@router.post("/webhook/whatsapp")
async def whatsapp_root(request: Request, db: AsyncSession = Depends(get_db),
                        From: str = Form(default=""), Body: str = Form(default="")):
    """Exact path registered in the Twilio console (ngrok)."""
    return await handle(request, From, Body, db)


@router.post("/api/v1/webhooks/whatsapp")
async def whatsapp_v1(request: Request, db: AsyncSession = Depends(get_db),
                      From: str = Form(default=""), Body: str = Form(default="")):
    return await handle(request, From, Body, db)
