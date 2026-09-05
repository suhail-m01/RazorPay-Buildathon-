"""Standalone worker entrypoint (docker-compose `worker` service).
Runs the same tick loop as the API process — safe because ticks are idempotent."""
from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.db import SessionLocal, init_db
from app.core.logging import get_logger

log = get_logger("worker")


async def main() -> None:
    from app.agent.state_machine import tick

    await init_db()
    interval = get_settings().tick_interval_minutes * 60
    log.info("worker.started", interval_s=interval)
    while True:
        try:
            async with SessionLocal() as db:
                summary = await tick(db, "http://localhost:3000")
                log.info("worker.tick", **summary)
        except Exception as e:
            log.error("worker.tick_failed", error=str(e)[:200])
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
