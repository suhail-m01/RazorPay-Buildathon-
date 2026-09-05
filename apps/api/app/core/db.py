"""Async engine/session factory. SQLite locally, Postgres via DATABASE_URL."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.models import base, recovery  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(base.Base.metadata.create_all)
        # Lightweight migration path (create_all won't ALTER existing tables on SQLite).
        from sqlalchemy import text

        for ddl in ("ALTER TABLE invoices ADD COLUMN razorpay_link_id TEXT",
                    "ALTER TABLE recovery_cases ADD COLUMN batch_tag VARCHAR(24)",
                    "ALTER TABLE customers ADD COLUMN billing_cycle VARCHAR(12)",
                    "ALTER TABLE invoices ADD COLUMN billing_cycle VARCHAR(12)",
                    "ALTER TABLE invoices ADD COLUMN title VARCHAR(160)",
                    "CREATE INDEX IF NOT EXISTS ix_recovery_cases_batch_tag ON recovery_cases (batch_tag"):
            try:
                await conn.execute(text(ddl))
            except Exception:
                pass  # column already exists
