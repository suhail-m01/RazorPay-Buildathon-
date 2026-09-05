"""RecoverPay AI — FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import get_logger, new_correlation_id

log = get_logger("main")
settings = get_settings()


async def _sync_loop():
    """Fast lane: poll Razorpay for captures every ~10s."""
    from app.agent.sync import reconcile_captures, sync_pending_invoices
    from app.core.db import SessionLocal

    while True:
        try:
            async with SessionLocal() as db:
                await sync_pending_invoices(
                    db,
                    "http://localhost:3000",
                )
                await reconcile_captures(db)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            log.error(
                "sync.loop_failed",
                error=str(e)[:200],
            )

        await asyncio.sleep(10)


async def _scheduler_loop():
    from app.agent.state_machine import tick
    from app.core.db import SessionLocal

    while True:
        try:
            async with SessionLocal() as db:
                await tick(
                    db,
                    "http://localhost:3000",
                )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            log.error(
                "scheduler.tick_failed",
                error=str(e)[:200],
            )

        await asyncio.sleep(
            settings.tick_interval_minutes * 60
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.backup import (
        make_backup,
        restore_if_needed,
        start_backup_loop,
    )

    restored = restore_if_needed()

    if restored:
        log.info(
            "durability.auto_restored",
            source=restored,
        )

    await init_db()
    make_backup()

    tasks = []

    # Scheduler is controlled by AUTO_TICK in .env.
    # Keep AUTO_TICK=false during local Vonage/webhook setup.
    if settings.auto_tick:
        scheduler_task = asyncio.create_task(
            _scheduler_loop()
        )

        sync_task = asyncio.create_task(
            _sync_loop()
        )

        backup_task = start_backup_loop(
            interval_s=60
        )

        tasks.extend(
            [
                scheduler_task,
                sync_task,
                backup_task,
            ]
        )

        log.info(
            "scheduler.started",
            interval_min=settings.tick_interval_minutes,
            fast_sync_seconds=10,
        )

    try:
        yield

    finally:
        for task in tasks:
            if task and not task.done():
                task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    cid = new_correlation_id()

    response = await call_next(request)

    response.headers["X-Correlation-ID"] = cid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.error(
        "api.unhandled",
        path=request.url.path,
        error=str(exc)[:300],
    )

    detail = (
        "Internal error — see server logs."
        if settings.environment == "production"
        else f"{type(exc).__name__}: {exc}"
    )

    return JSONResponse(
        {"detail": detail},
        status_code=500,
    )


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": settings.app_name,
        "version": settings.app_version,
        "time": datetime.now(timezone.utc).isoformat(),
        "modes": {
            "razorpay": (
                "live"
                if settings.razorpay_live
                else "test"
            ),
            "email": (
                "resend"
                if settings.resend_api_key
                else "queued"
            ),
            "llm": bool(
                settings.openai_api_key
                or settings.anthropic_api_key
                or settings.gemini_api_key
            ),
            "scheduler": settings.auto_tick,
        },
    }


@app.get("/api/v1/health")
async def health_v1():
    return await health()

from app.api.v1.routes import (
    admin,
    agent,
    analytics,
    auth,
    batch,
    cases,
    events,
    pay,
    payments,
    portal,
    setup,
    webhooks,
)

from app.api.v1.routes.whatsapp_inbound import (
    router as _wa_router,
)

from app.api.v1.routes.twilio import (
    router as _twilio_router,
)

API_PREFIX = "/api/v1"


app.include_router(
    auth.router,
    prefix=API_PREFIX,
)

app.include_router(
    cases.router,
    prefix=API_PREFIX,
)

app.include_router(
    portal.router,
    prefix=API_PREFIX,
)

app.include_router(
    webhooks.router,
    prefix=API_PREFIX,
)

app.include_router(
    admin.router,
    prefix=API_PREFIX,
)

app.include_router(
    analytics.router,
    prefix=API_PREFIX,
)

app.include_router(
    agent.router,
    prefix=API_PREFIX,
)

app.include_router(
    events.router,
    prefix=API_PREFIX,
)

app.include_router(
    setup.router,
    prefix=API_PREFIX,
)

app.include_router(
    payments.router,
    prefix=API_PREFIX,
)

app.include_router(
    pay.router,
    prefix=API_PREFIX,
)

app.include_router(
    batch.router,
    prefix=API_PREFIX,
)


from app.api.v1.routes import vonage as _vonage


app.add_api_route(
    f"{API_PREFIX}/webhooks/vonage/whatsapp",
    _vonage.inbound,
    methods=["POST"],
    tags=["vonage"],
)

app.add_api_route(
    f"{API_PREFIX}/webhooks/vonage/whatsapp/status",
    _vonage.status,
    methods=["POST"],
    tags=["vonage"],
)

app.add_api_route(
    f"{API_PREFIX}/webhooks/vonage/voice/event",
    _vonage.voice_event,
    methods=["GET", "POST"],
    tags=["vonage"],
)



app.include_router(_wa_router)
app.include_router(_twilio_router)