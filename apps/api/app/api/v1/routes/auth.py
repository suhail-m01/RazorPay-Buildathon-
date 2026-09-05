"""Merchant auth: register / login / refresh / logout / me. JWT in httpOnly cookies."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import MERCHANT_COOKIE, REFRESH_COOKIE, get_current_user
from app.core.logging import get_logger
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.base import Merchant, MerchantUser
from app.schemas import MerchantLogin, MerchantRegister

log = get_logger("api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    """SameSite=None + Secure + Partitioned (CHIPS): the session also survives inside
    cross-site preview iframes. Browsers that refuse even partitioned cookies are
    covered by the signed-token fallback the client sends as x-rp-token."""
    response.headers.append(
        "Set-Cookie",
        f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=None; Secure; Partitioned",
    )


def _issue(response: Response, user: MerchantUser) -> dict:
    access = create_access_token(user.id, user.role, user.merchant_id)
    refresh = create_refresh_token(user.id)
    _set_cookie(response, MERCHANT_COOKIE, access, 15 * 60)
    _set_cookie(response, REFRESH_COOKIE, refresh, 7 * 24 * 3600)
    return {"ok": True, "name": user.name, "role": user.role, "redirect": "/app", "token": access, "refresh": refresh}


@router.post("/register")
async def register(body: MerchantRegister, response: Response, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    if await db.scalar(select(MerchantUser).where(MerchantUser.email == email)):
        raise HTTPException(409, "This email already has an account — please log in.")
    merchant = (await db.execute(select(Merchant).where(Merchant.name == body.company.strip()))).scalar_one_or_none()
    if not merchant:
        merchant = Merchant(name=body.company.strip())
        db.add(merchant)
        await db.flush()
    user = MerchantUser(merchant_id=merchant.id, email=email, name=body.name,
                        password_hash=hash_password(body.password), role=body.role if body.role in ("admin", "recovery_agent", "viewer") else "admin")
    db.add(user)
    await db.commit()
    log.info("merchant.registered", email=email, merchant=merchant.name)
    return _issue(response, user)


@router.post("/login")
async def login(body: MerchantLogin, response: Response, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    user = (await db.execute(select(MerchantUser).where(MerchantUser.email == email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    return _issue(response, user)


@router.post("/refresh")
async def refresh(response: Response, rp_refresh: str | None = None, body: dict | None = None, db: AsyncSession = Depends(get_db)):
    raw = rp_refresh or (body or {}).get("refresh")
    if not raw:
        raise HTTPException(401, "No refresh token.")
    payload = decode_token(raw, "refresh")
    if not payload:
        raise HTTPException(401, "Refresh token expired — log in again.")
    user = await db.get(MerchantUser, payload["sub"])
    if not user:
        raise HTTPException(401, "Account not found.")
    return _issue(response, user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(MERCHANT_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: MerchantUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    merchant = await db.get(Merchant, user.merchant_id)
    return {"ok": True, "name": user.name, "email": user.email, "role": user.role, "merchant": merchant.name if merchant else ""}
