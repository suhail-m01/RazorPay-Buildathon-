"""LLM client — OpenAI or Anthropic, strict JSON outputs. Returns None when unset/failing."""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("integ.llm")


async def llm_json(prompt: str, system: str | None = None, gemini_key: str | None = None) -> dict[str, Any] | None:
    s = get_settings()
    key = gemini_key or s.gemini_api_key
    if key:
        import asyncio

        models = [s.gemini_model or "gemini-3.6-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
        body = {
            **({"systemInstruction": {"parts": [{"text": (system or "") + " Reply with JSON only."}]}} if system else {}),
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        for attempt in range(3):  # retries with backoff — the free tier rate-limits under load
            for model in models:
                try:
                    async with httpx.AsyncClient(timeout=40) as c:
                        r = await c.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                            params={"key": key}, json=body,
                        )
                        if r.status_code == 200:
                            text = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
                            return json.loads(text)
                        if r.status_code not in (429, 500, 503):  # only retry transient states
                            log.warning("llm.gemini_http_error", model=model, status=r.status_code, body=r.text[:120])
                            break
                        log.warning("llm.gemini_transient", model=model, status=r.status_code)
                except Exception as e:
                    log.warning("llm.gemini_exception", model=model, error=str(e)[:100])
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
    if s.openai_api_key:
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {s.openai_api_key}"},
                    json={"model": s.openai_model, "response_format": {"type": "json_object"},
                          "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]},
                )
                if r.status_code == 200:
                    return json.loads(r.json()["choices"][0]["message"]["content"])
            log.warning("llm.openai_http_error", status=r.status_code)
        except Exception as e:
            log.warning("llm.openai_exception", error=str(e)[:120])
    if s.anthropic_api_key:
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01"},
                    json={"model": s.anthropic_model, "max_tokens": 400,
                          "system": (system or "") + " Reply with JSON only.",
                          "messages": [{"role": "user", "content": prompt}]},
                )
                if r.status_code == 200:
                    text = r.json()["content"][0]["text"]
                    return json.loads(text[text.find("{"): text.rfind("}") + 1])
        except Exception as e:
            log.warning("llm.anthropic_exception", error=str(e)[:120])
    return None
