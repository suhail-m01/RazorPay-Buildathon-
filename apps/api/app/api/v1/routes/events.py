"""Live pipeline feed — SSE (proxy-friendly) plus a native WebSocket endpoint."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from app.agent.audit import subscribe, unsubscribe

router = APIRouter(tags=["events"])


@router.get("/events/stream")
async def sse_stream():
    q = await subscribe()

    async def gen():
        yield {"event": "hello", "data": json.dumps({"ok": True})}
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=20)
                    yield {"event": "audit", "data": json.dumps(item, ensure_ascii=False)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            unsubscribe(q)

    return EventSourceResponse(gen())


@router.websocket("/events/ws")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    q = await subscribe()
    try:
        await ws.send_text(json.dumps({"type": "hello"}))
        while True:
            item = await asyncio.wait_for(q.get(), timeout=30)
            await ws.send_text(json.dumps(item, ensure_ascii=False))
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        unsubscribe(q)
