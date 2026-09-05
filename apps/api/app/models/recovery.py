"""Recovery entities: cases, promises, append-only audit, tokens, approvals, outbox."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Customer, Invoice, utcnow


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"case_{__import__('uuid').uuid4().hex[:11]}")
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    batch_tag: Mapped[str | None] = mapped_column(String(24), index=True)  # evaluation-batch rows only
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    type: Mapped[str] = mapped_column(String(24), default="invoice_overdue")
    # payment_failed | checkout_abandoned | subscription_failed | mandate_failed | invoice_overdue
    amount_paise: Mapped[int] = mapped_column(Integer)
    failure_reason_code: Mapped[str | None] = mapped_column(String(48))
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    root_cause: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str] = mapped_column(String(20), default="detected")
    # detected | diagnosed | email_sent | promise_wait | whatsapp_sent | voice_attempted | recovered | escalated | stopped | closed
    recovery_channel: Mapped[str | None] = mapped_column(String(12))
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | recovered | escalated | stopped | closed
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="cases")
    invoice: Mapped[Invoice] = relationship(back_populates="cases")
    promises: Mapped[list[PromiseToPay]] = relationship(back_populates="case")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="case")
    approvals: Mapped[list[HumanApprovalRequest]] = relationship(back_populates="case")
    receipts: Mapped[list[Receipt]] = relationship(back_populates="case")


class PromiseToPay(Base):
    __tablename__ = "promises_to_pay"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"prm_{__import__('uuid').uuid4().hex[:11]}")
    case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), index=True)
    promised_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    promised_amount_paise: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | kept | broken | rejected
    reject_reason: Mapped[str | None] = mapped_column(String(48))
    utterance: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[RecoveryCase] = relationship(back_populates="promises")


class AuditLog(Base):
    """Append-only, hash-chained. id is a monotonic integer → natural chain order."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"), index=True)
    actor: Mapped[str] = mapped_column(String(24))  # agent | ai | system | human | customer | razorpay
    action: Mapped[str] = mapped_column(String(48))
    reason_code: Mapped[str | None] = mapped_column(String(48))
    channel: Mapped[str | None] = mapped_column(String(12))
    message_sent: Mapped[str | None] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_checks: Mapped[dict[str, Any] | None] = mapped_column(__import__("sqlalchemy").JSON, default=None)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[RecoveryCase | None] = relationship(back_populates="audit_logs")


class PortalToken(Base):
    __tablename__ = "portal_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="tokens")


class HumanApprovalRequest(Base):
    __tablename__ = "human_approval_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"apr_{__import__('uuid').uuid4().hex[:11]}")
    case_id: Mapped[str] = mapped_column(ForeignKey("recovery_cases.id"), index=True)
    suggested_action: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | rejected
    reviewer_id: Mapped[str | None] = mapped_column(String(32))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[RecoveryCase] = relationship(back_populates="approvals")


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    id: Mapped[str] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(12))  # email | sms | whatsapp | voice
    recipient: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued | sent | simulated | failed | cancelled
    case_id: Mapped[str | None] = mapped_column(String(32))
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"rcp_{__import__('uuid').uuid4().hex[:11]}")
    payment_id: Mapped[str] = mapped_column(String(60), unique=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_cases.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    emailed_to: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[RecoveryCase] = relationship(back_populates="receipts")


class Playbook(Base):
    __tablename__ = "playbooks"
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="active")
    traffic_share: Mapped[int] = mapped_column(Integer, default=0)
    definition: Mapped[dict[str, Any]] = mapped_column(__import__("sqlalchemy").JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(48))
    provider: Mapped[str] = mapped_column(String(16), default="razorpay")
    signature_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[str | None] = mapped_column(Text)
    handled: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
