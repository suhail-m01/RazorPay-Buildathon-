"""Pydantic v2 request/response schemas — strict: extra fields rejected everywhere."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MerchantRegister(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    company: str = Field(min_length=2, max_length=160)
    role: str = "admin"


class MerchantLogin(Strict):
    email: EmailStr
    password: str = Field(min_length=1)


class PortalRegister(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    phone: str = Field(min_length=10, max_length=16)


class PortalLogin(Strict):
    email: EmailStr
    password: str = Field(min_length=1)


class ReplyIn(Strict):
    text: str = Field(min_length=1, max_length=1000)


class AdvanceIn(Strict):
    pass


class ApprovalIn(Strict):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=3, max_length=300)


class InjectIn(Strict):
    case_type: str = Field(pattern="^(payment_failed|checkout_abandoned|subscription_failed|mandate_failed|invoice_overdue|random)$", default="random")


class CheckoutIn(Strict):
    order_id: str
    payment_id: str | None = None
    signature: str | None = None
    # When Razorpay's hosted checkout cannot load (e.g. an offline embedded preview),
    # the customer may complete via the in-app capture path. Same service as the
    # webhook; audited as a test capture. Real hosted checkout is always preferred.
    test_fallback: bool = False


class OrderIn(Strict):
    case_id: str | None = None
    invoice_id: str | None = None
    amount_paise: int | None = Field(default=None, gt=0)  # partial payment for large B2B invoices
