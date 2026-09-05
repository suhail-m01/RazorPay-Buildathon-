"""Core entities: merchants, customers, products, subscriptions, invoices, portal accounts."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"mch_{__import__('uuid').uuid4().hex[:12]}")
    name: Mapped[str] = mapped_column(String(160))
    gstin: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list[MerchantUser]] = relationship(back_populates="merchant")
    customers: Mapped[list[Customer]] = relationship(back_populates="merchant")


class MerchantUser(Base):
    __tablename__ = "merchant_users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"usr_{__import__('uuid').uuid4().hex[:12]}")
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="admin")  # admin | recovery_agent | viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant: Mapped[Merchant] = relationship(back_populates="users")


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"cst_{__import__('uuid').uuid4().hex[:12]}")
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    preferred_channel: Mapped[str] = mapped_column(String(12), default="email")  # email | sms | whatsapp
    preferred_language: Mapped[str] = mapped_column(String(8), default="en-IN")
    consent_email: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    # Recurring arrangement: monthly | yearly | one_time (null = unknown yet)
    billing_cycle: Mapped[str | None] = mapped_column(String(12))
    # HARD GATE: only live contacts ever trigger real dispatch — enforced inside the Act layer.
    is_demo_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant: Mapped[Merchant] = relationship(back_populates="customers")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="customer")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="customer")
    cases: Mapped[list[RecoveryCase]] = relationship(back_populates="customer")
    account: Mapped[PortalAccount | None] = relationship(back_populates="customer")
    tokens: Mapped[list[PortalToken]] = relationship(back_populates="customer")


class PortalAccount(Base):
    """Customer-portal login (email + password). Magic links remain an alternative path."""
    __tablename__ = "portal_accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"pac_{__import__('uuid').uuid4().hex[:12]}")
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), unique=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="account")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"prd_{__import__('uuid').uuid4().hex[:12]}")
    name: Mapped[str] = mapped_column(String(160))
    price_paise: Mapped[int] = mapped_column(Integer)
    billing_cycle: Mapped[str] = mapped_column(String(16), default="monthly")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="product")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"sub_{__import__('uuid').uuid4().hex[:12]}")
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    months_remaining: Mapped[int] = mapped_column(Integer, default=1)
    monthly_amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | paused | cancelled
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    product: Mapped[Product] = relationship(back_populates="subscriptions")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="subscription")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"inv_{__import__('uuid').uuid4().hex[:12]}")
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | paid | overdue | failed
    razorpay_order_id: Mapped[str | None] = mapped_column(String(60), index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(60))
    razorpay_link_id: Mapped[str | None] = mapped_column(String(60))
    billing_cycle: Mapped[str | None] = mapped_column(String(12))  # monthly | yearly | one_time
    title: Mapped[str | None] = mapped_column(String(160))  # what this payment is FOR
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped[Customer] = relationship(back_populates="invoices")
    subscription: Mapped[Subscription | None] = relationship(back_populates="invoices")
    cases: Mapped[list[RecoveryCase]] = relationship(back_populates="invoice")
