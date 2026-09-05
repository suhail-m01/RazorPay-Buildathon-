"""FastAPI dependencies: auth (merchant JWT / customer portal), RBAC, client IP."""
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models.base import Customer, MerchantUser, PortalAccount

MERCHANT_COOKIE = "rp_access"
REFRESH_COOKIE = "rp_refresh"
PORTAL_COOKIE = "rp_portal"


async def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "local"


async def _user_from_cookie(token: str | None, db: AsyncSession) -> MerchantUser | None:
    if not token:
        return None
    payload = decode_token(token, "access")
    if not payload:
        return None
    user = await db.get(MerchantUser, payload["sub"])
    return user


async def get_current_user(
    rp_access: str | None = Cookie(default=None),
    x_rp_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> MerchantUser:
    token = rp_access or x_rp_token
    user = await _user_from_cookie(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_role(roles: tuple[str, ...]):
    async def _guard(user: MerchantUser = Depends(get_current_user)) -> MerchantUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user

    return _guard


async def get_portal_customer(
    rp_portal: str | None = Cookie(default=None),
    x_rp_portal: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    token = rp_portal or x_rp_portal
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token, "portal")
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired — log in again")
    account = await db.get(PortalAccount, payload["sub"])
    if not account:
        raise HTTPException(status_code=401, detail="Account not found")
    customer = await db.get(Customer, account.customer_id)
    if not customer:
        raise HTTPException(status_code=401, detail="No billing profile")
    return customer
