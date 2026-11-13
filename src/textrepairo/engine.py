"""The repair engine: turns text into improved English using a local llama-server."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import AsyncIterator, Callable

import httpx

from . import models as models_mod
from .config import Settings, load_settings
from .hardware import Hardware, detect
from .prompts import MODES, build_messages
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

    # ------------------------------------------------------------ repair
    async def stream(self, text: str, mode: str = "fix", settings: Settings | None = None
                     ) -> AsyncIterator[dict]:
        """Yield events: {event: 'partial', text} ... then {event: 'done', ...}."""
        if mode not in MODES:
            raise EngineError(f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}")
        settings = settings or load_settings()
        if not text.strip():
            yield {"event": "done", "text": text, "warnings": [], "diff": [], "seconds": 0.0,
                   "tokens": 0, "mode": mode, "model": settings.model_id}
            return
        import asyncio
        base, key, hybrid = await asyncio.to_thread(self.ensure_started, settings)
        started = time.time()
        chunks = split_chunks(text)
        done_text = ""
        warnings: list[str] = []
        total_tokens = 0
        for chunk in chunks:
            if not chunk.text.strip():
                done_text += chunk.text + chunk.sep
                continue
            masked, store = mask(chunk.text)
            out = ""
            async for piece in self._complete(base, key, hybrid, mode, masked, settings):
                out += piece
                total_tokens += 1
                partial = hide_partial_placeholder(clean_output(out))
                shown, _ = unmask(partial, store)
                yield {"event": "partial", "text": done_text + shown}
            final = clean_output(out)
            restored, missing = unmask(final, store)
            if missing:
                warnings.append("Some links or code snippets were dropped by the model; "
                                "they were restored in place.")
                for k in missing:  # put dropped spans at the end so nothing is lost
                    restored += " " + store[k]
            warnings += [w for w in check_output(chunk.text, restored) if w not in warnings]
            done_text += restored + chunk.sep
        result = done_text
        yield {
            "event": "done", "text": result, "warnings": warnings,
            "diff": diff_ops(text, result), "seconds": round(time.time() - started, 2),
            "tokens": total_tokens, "mode": mode, "model": settings.model_id,
        }

    async def _complete(self, base: str, key: str, hybrid: bool, mode: str, text: str,
                        settings: Settings) -> AsyncIterator[str]:
        m = MODES[mode]
        est_tokens = max(64, len(text) // 2)
        body: dict = {
            "messages": build_messages(mode, text),
            "stream": True,
            "temperature": m.temperature,
            "top_p": 0.9,
            "max_tokens": min(2048, est_tokens * 3 + 128),
            "cache_prompt": True,
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
                        delta = json.loads(payload)["choices"][0].get("delta", {})
                    except (ValueError, KeyError, IndexError):
                        continue
                    piece = delta.get("content")
                    if piece:
                        yield piece
        except httpx.HTTPError as e:
            raise EngineError(f"Lost connection to the engine: {e}") from e

    async def repair(self, text: str, mode: str = "fix", settings: Settings | None = None,
                     on_partial: Callable[[str], None] | None = None) -> RepairResult:
        final: dict | None = None
        async for ev in self.stream(text, mode, settings):
            if ev["event"] == "partial" and on_partial:
                on_partial(ev["text"])
            elif ev["event"] == "done":
                final = ev
        assert final is not None
        return RepairResult(final["text"], final["warnings"], final["diff"], final["seconds"],
                            final["tokens"], final["mode"], final["model"])
