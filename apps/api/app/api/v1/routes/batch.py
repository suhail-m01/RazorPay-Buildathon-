"""Batch endpoints — run the evaluation batch and read "The Bar" report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.batch import batch_report, list_batches, run_batch
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.base import MerchantUser

router = APIRouter(prefix="/batch", tags=["batch"])


class RunIn(BaseModel):
    size: int = Field(default=40, ge=10, le=120)


def _base(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or ("https" if "e2b.app" in host else "http")
    return f"{proto}://{host}" if host else str(request.base_url).rstrip("/")


@router.post("/run")
async def run(body: RunIn, request: Request, db: AsyncSession = Depends(get_db),
              user: MerchantUser = Depends(get_current_user)):
    """Generate + run a labeled evaluation batch through the REAL agent (sends are gated)."""
    out = await run_batch(db, user.merchant_id, _base(request), size=body.size)
    return {"ok": True, **out}


@router.get("/report")
async def report(tag: str | None = None, db: AsyncSession = Depends(get_db),
                 user: MerchantUser = Depends(get_current_user)):
    from app.agent.batch import latest_batch_tag

    t = tag or await latest_batch_tag(db)
    if not t:
        raise HTTPException(404, "No batches yet — run one first.")
    return {"ok": True, **await batch_report(db, t)}


@router.get("/list")
async def batches(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    return {"ok": True, "batches": await list_batches(db)}
