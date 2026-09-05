from fastapi import APIRouter

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
    vonage,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(portal.router)
api_router.include_router(webhooks.router)
api_router.include_router(admin.router)
api_router.include_router(analytics.router)
api_router.include_router(agent.router)
api_router.include_router(events.router)
api_router.include_router(setup.router)
api_router.include_router(payments.router)
api_router.include_router(pay.router)
api_router.include_router(batch.router)
api_router.include_router(vonage.router)