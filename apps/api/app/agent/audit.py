"""Append-only, hash-chained audit logger + live event bus."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.recovery import AuditLog

log = get_logger("agent.audit")

# In-process pub/sub for the live dashboard feed (swap for Redis pub/sub at scale).
_subscribers: set[asyncio.Queue] = set()


def publish_event(event: dict[str, Any]) -> None:
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def _norm_iso(dt: datetime) -> str:
    """UTC-normalised, offset-free ISO — identical whether the datetime is aware or
    read back naive from SQLite (which drops the offset)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def _canonical(prev_hash: str | None, case_id: str | None, actor: str, action: str, reason_code: str | None,
               channel: str | None, message: str | None, simulated: bool, checks: dict | None, ts: str) -> str:
    return json.dumps(
        [prev_hash, case_id, actor, action, reason_code, channel, message, simulated, checks, ts],
        sort_keys=True, ensure_ascii=False,
    )


async def append_audit(
    db: AsyncSession,
    *,
    case_id: str | None,
    actor: str,
    action: str,
    reason_code: str | None = None,
    channel: str | None = None,
    message_sent: str | None = None,
    simulated: bool = False,
    compliance_checks: dict[str, Any] | None = None,
    created_at: datetime | None = None,
    commit: bool = True,
) -> AuditLog:
    ts = created_at or datetime.now(timezone.utc)
    prev = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))).scalar_one_or_none()
    prev_hash = prev.hash if prev else None
    core = _canonical(prev_hash, case_id, actor, action, reason_code, channel, message_sent, simulated, compliance_checks, _norm_iso(ts))
    row = AuditLog(
        case_id=case_id, actor=actor, action=action, reason_code=reason_code, channel=channel,
        message_sent=message_sent, simulated=simulated, compliance_checks=compliance_checks,
        prev_hash=prev_hash, hash=hashlib.sha256(core.encode()).hexdigest(), created_at=ts,
    )
    db.add(row)
    if commit:
        await db.commit()
    publish_event({"type": "audit", "case_id": case_id, "actor": actor, "action": action,
                   "channel": channel, "simulated": simulated, "reason_code": reason_code, "ts": ts.isoformat()})
    log.info("audit.append", case_id=case_id, action=action, actor=actor, simulated=simulated, reason=reason_code)
    return row


async def verify_chain(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id.asc()))).scalars().all()
    prev: str | None = None
    for r in rows:
        core = _canonical(r.prev_hash, r.case_id, r.actor, r.action, r.reason_code, r.channel,
                          r.message_sent, r.simulated, r.compliance_checks, _norm_iso(r.created_at))
        expected = hashlib.sha256(core.encode()).hexdigest()
        if r.hash != expected or r.prev_hash != prev:
            return {"ok": False, "checked": len(rows), "broken_at_id": r.id}
        prev = r.hash
    return {"ok": True, "checked": len(rows), "head": prev}
