# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""The repair engine: turns text into improved English using a local llama-server."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import AsyncIterator, Callable

import httpx

from . import models as models_mod
from . import packs
from .config import MAX_TEXT_CHARS, Settings, load_settings
from .hardware import Hardware, detect
from .humanize import humanize_pass
from .progress import ProgressTracker
from .prompts import (FORMALITY, STYLES, build_messages, expected_ratio, resolve_style)
from .runtime import LlamaServer, RuntimeError_, choose_backend, find_runtime
from .textproc import (check_output, clean_output, diff_ops, hide_partial_placeholder, mask,
                       split_chunks, unmask)


class EngineError(RuntimeError):
    pass


@dataclass
class RepairResult:
    text: str
    warnings: list[str]
    diff: list[dict]
    seconds: float
    tokens: int
    mode: str
    model: str


class Engine:
    """Lazy wrapper: starts llama-server on first use and keeps it loaded."""

    def __init__(self, server: LlamaServer | None = None, hardware: Hardware | None = None) -> None:
        self.server = server or LlamaServer()
        self._hw = hardware
        self._client: httpx.AsyncClient | None = None
        self._lock: asyncio.Lock | None = None  # one repair at a time

    # ------------------------------------------------------------ status
    @property
    def hw(self) -> Hardware:
        if self._hw is None:
            self._hw = detect()
        return self._hw

    def ensure_started(self, settings: Settings | None = None) -> tuple[str, str, bool]:
        """Start the model server if needed. Returns (base_url, api_key, thinking_hybrid)."""
        settings = settings or load_settings()
        try:
            path, spec = models_mod.resolve_model(settings.model_id)
        except models_mod.ModelError as e:
            raise EngineError(str(e)) from e
        backend = choose_backend(settings.backend, self.hw)
        if find_runtime(backend) is None:
            if backend != "cpu" and find_runtime("cpu"):
                backend = "cpu"
            else:
                raise EngineError(
                    "The text engine (llama.cpp) is not installed yet. Run setup from Settings, "
                    "or: textrepairo runtime install")
        try:
            info = self.server.start(path, backend, settings, self.hw)
        except RuntimeError_ as e:
            raise EngineError(str(e)) from e
        hybrid = bool(spec and spec.thinking_hybrid) or (spec is None and "qwen3" in path.name.lower()
                                                         and "instruct-2507" not in path.name.lower())
        return info.base_url, info.api_key, hybrid

    def shutdown(self) -> None:
        self.server.stop()

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))
        return self._client

    def _repair_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ------------------------------------------------------------ repair
    async def stream(self, text: str, mode: str = "fix", settings: Settings | None = None,
                     formality: str | None = None, target: str | None = None,
                     max_chars: int = MAX_TEXT_CHARS) -> AsyncIterator[dict]:
        """Yield events: progress / partial ... then one done event.

        Events: {event: 'progress', pct, chunk, chunks, phase, tokens_per_s, eta_s}
                {event: 'partial', text}
                {event: 'done', text, warnings, diff, seconds, tokens, mode, formality, model, notes}
        """
        mode = resolve_style(mode)
        if mode not in STYLES:
            raise EngineError(f"Unknown style '{mode}'. Use one of: {', '.join(STYLES)}")
        settings = settings or load_settings()
        formality = formality or settings.default_formality
        if formality not in FORMALITY:
            raise EngineError(f"Unknown formality '{formality}'. Use one of: {', '.join(FORMALITY)}")
        if len(text) > max_chars:
            raise EngineError(f"This text has {len(text):,} characters. The limit is {max_chars:,} "
                              "per repair. Split it into parts and repair them one by one.")
        if not text.strip():
            yield {"event": "done", "text": text, "warnings": [], "diff": [], "seconds": 0.0,
                   "tokens": 0, "mode": mode, "formality": formality, "model": settings.model_id,
                   "notes": 0}
            return
        async with self._repair_lock():
            async for ev in self._stream_locked(text, mode, settings, formality, target):
                yield ev

    async def _stream_locked(self, text: str, mode: str, settings: Settings, formality: str,
                             target: str | None) -> AsyncIterator[dict]:
        started = time.time()
        fut = asyncio.ensure_future(asyncio.to_thread(self.ensure_started, settings))
        while True:  # model loading can't be measured: report elapsed time only, never a percentage
            done, _ = await asyncio.wait({fut}, timeout=0.5)
            if done:
                break
            yield {"event": "progress", "phase": "loading", "pct": None,
                   "elapsed_s": round(time.time() - started, 1)}
        base, key, hybrid = fut.result()

        chunks = split_chunks(text)
        tracker = ProgressTracker([len(c.text) if c.text.strip() else 0 for c in chunks])
        hints = packs.match(text)
        ratio = expected_ratio(mode, target)
        done_text = ""
        warnings: list[str] = []
        total_tokens = 0
        last_emit = 0.0
        yield tracker.snapshot()
        for i, chunk in enumerate(chunks):
            if not chunk.text.strip():
                done_text += chunk.text + chunk.sep
                continue
            tracker.start_chunk(i)
            masked, store = mask(chunk.text)
            expected = max(8.0, await self._count_tokens(base, key, masked) * ratio)
            out = ""
            finish: str | None = None
            ntok = 0
            async for kind, a, b in self._complete(base, key, hybrid, mode, masked, settings, formality,
                                                   hints, target):
                if kind == "prompt":
                    tracker.reading_progress(int(a), int(b))
                elif kind == "text":
                    out += str(a)
                    ntok += 1
                    total_tokens += 1
                    tracker.writing_progress(ntok, expected)
                    partial = hide_partial_placeholder(clean_output(out))
                    shown, _ = unmask(partial, store)
                    yield {"event": "partial", "text": done_text + shown}
                elif kind == "end":
                    finish = str(a) if a else None
                now = time.monotonic()
                if now - last_emit >= 0.15:
                    last_emit = now
                    yield tracker.snapshot()
            final = humanize_pass(chunk.text, clean_output(out))
            restored, missing = unmask(final, store)
            if missing:
                warnings.append("Some links or code snippets were dropped by the model; "
                                "they were restored in place.")
                for k in missing:  # put dropped spans at the end so nothing is lost
                    restored += " " + store[k]
            if finish == "length":
                warnings.append("The result was cut off because it got too long. Please review the end.")
            warnings += [w for w in check_output(chunk.text, restored) if w not in warnings]
            done_text += restored + chunk.sep
            tracker.finish_chunk()
        tracker.finish()
        yield tracker.snapshot()
        yield {
            "event": "done", "text": done_text, "warnings": warnings,
            "diff": diff_ops(text, done_text), "seconds": round(time.time() - started, 2),
            "tokens": total_tokens, "mode": mode, "formality": formality, "model": settings.model_id,
            "notes": len(hints),
        }

    async def _count_tokens(self, base: str, key: str, text: str) -> int:
        """Real token count from the engine; falls back to a character estimate if unavailable."""
        try:
            r = await self._http().post(f"{base}/tokenize", json={"content": text},
                                        headers={"Authorization": f"Bearer {key}"}, timeout=10.0)
            if r.status_code == 200:
                n = len(r.json().get("tokens") or [])
                if n:
                    return n
        except (httpx.HTTPError, ValueError):
            pass
        return max(1, int(len(text) / 3.2))

    async def _complete(self, base: str, key: str, hybrid: bool, mode: str, text: str,
                        settings: Settings, formality: str, hints: list[str], target: str | None
                        ) -> AsyncIterator[tuple[str, object, object]]:
        """Yield ('prompt', processed, total) | ('text', piece, None) | ('end', finish_reason, None)."""
        style = STYLES[mode]
        est_tokens = max(64, len(text) // 2)
        body: dict = {
            "messages": build_messages(mode, text, formality, hints, target),
            "stream": True,
            "temperature": style.temperature,
            "top_p": 0.9,
            "max_tokens": min(2048, est_tokens * 3 + 128),
            "cache_prompt": True,
            "return_progress": True,
        }
        if hybrid:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Authorization": f"Bearer {key}"}
        try:
            async with self._http().stream("POST", f"{base}/v1/chat/completions", json=body,
                                           headers=headers) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode("utf-8", "replace")[:300]
                    raise EngineError(f"The engine returned an error ({resp.status_code}): {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except ValueError:
                        continue
                    pp = obj.get("prompt_progress")
                    if isinstance(pp, dict) and pp.get("total"):
                        yield ("prompt", pp.get("processed", 0), pp["total"])
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    piece = (choices[0].get("delta") or {}).get("content")
                    if piece:
                        yield ("text", piece, None)
                    if choices[0].get("finish_reason"):
                        yield ("end", choices[0]["finish_reason"], None)
        except httpx.HTTPError as e:
            raise EngineError(f"Lost connection to the engine: {e}") from e

    async def repair(self, text: str, mode: str = "fix", settings: Settings | None = None,
                     on_partial: Callable[[str], None] | None = None, formality: str | None = None,
                     target: str | None = None, max_chars: int = MAX_TEXT_CHARS) -> RepairResult:
        final: dict | None = None
        async for ev in self.stream(text, mode, settings, formality, target, max_chars):
            if ev["event"] == "partial" and on_partial:
                on_partial(ev["text"])
            elif ev["event"] == "done":
                final = ev
        assert final is not None
        return RepairResult(final["text"], final["warnings"], final["diff"], final["seconds"],
                            final["tokens"], final["mode"], final["model"])
