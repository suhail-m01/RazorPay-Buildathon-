"""structlog JSON logging with per-request correlation IDs."""
import contextvars
import uuid

import structlog

correlation_id = contextvars.ContextVar("correlation_id", default="-")

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    cache_logger_on_first_use=True,
)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name).bind(corr=correlation_id.get())


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid
