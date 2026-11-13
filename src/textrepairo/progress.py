# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Honest progress for a repair.

Rules this module follows (so the bar is never fake):
  * Work is split into chunks. A chunk's weight is its share of the input characters (exact).
  * Inside a chunk: the "reading" part uses the engine's real prompt-processing counters. The
    "writing" part compares generated tokens with the expected length, which is an ESTIMATE, so it
    is capped below 100% until the chunk is really finished.
  * The overall percentage never goes backwards and only reaches 100 when the work is done.
  * Time left is computed from measured speed and only shown once there is enough data.
  * Loading the model cannot be measured, so it reports no percentage, only elapsed seconds.
"""

from __future__ import annotations

import math
import time

READING_SHARE = 0.20  # share of a chunk's bar used by the reading phase
WRITING_CAP = 0.99  # a chunk's writing part never reports more than this before it finishes


def writing_fraction(tokens: int, expected: float) -> float:
    """0..WRITING_CAP. Linear up to 90% of the expectation, then eases toward the cap."""
    if expected <= 0:
        return 0.0
    r = tokens / expected
    if r <= 0.9:
        return max(0.0, r)
    return 0.9 + (WRITING_CAP - 0.9) * (1 - math.exp(-(r - 0.9) * 3))


class ProgressTracker:
    def __init__(self, weights: list[int], clock=time.monotonic) -> None:
        self.weights = [max(0, w) for w in weights]
        self.total = max(1, sum(self.weights))
        self._clock = clock
        self._t0 = clock()
        self.index = -1
        self.done_weight = 0
        self.reading = 0.0
        self.writing = 0.0
        self.phase = "reading"
        self.tokens = 0
        self._write_t0: float | None = None
        self._last_pct = 0.0
        self.finished = False

    # ---- chunk lifecycle
    def start_chunk(self, index: int) -> None:
        self.index = index
        self.reading = 0.0
        self.writing = 0.0
        self.tokens = 0
        self.phase = "reading"
        self._write_t0 = None

    def reading_progress(self, processed: int, total: int) -> None:
        self.phase = "reading"
        if total > 0:
            self.reading = max(self.reading, min(1.0, processed / total))

    def writing_progress(self, tokens: int, expected: float) -> None:
        if self._write_t0 is None:
            self._write_t0 = self._clock()
            self.reading = 1.0
        self.phase = "writing"
        self.tokens = tokens
        self.writing = max(self.writing, writing_fraction(tokens, expected))

    def finish_chunk(self) -> None:
        if 0 <= self.index < len(self.weights):
            self.done_weight += self.weights[self.index]
        self.reading = self.writing = 0.0
        self.tokens = 0
        self._write_t0 = None

    def finish(self) -> None:
        self.finished = True

    # ---- reporting
    @property
    def fraction(self) -> float:
        if self.finished:
            return 1.0
        cur = 0.0
        if 0 <= self.index < len(self.weights):
            inner = READING_SHARE * self.reading + (1 - READING_SHARE) * self.writing
            cur = self.weights[self.index] * inner
        f = (self.done_weight + cur) / self.total
        f = min(f, 0.999)  # 100% is reserved for "done"
        self._last_pct = max(self._last_pct, f)
        return self._last_pct

    def tokens_per_second(self) -> float | None:
        if self._write_t0 is None or self.tokens < 4:
            return None
        dt = self._clock() - self._write_t0
        return self.tokens / dt if dt > 0.2 else None

    def eta_seconds(self) -> float | None:
        """Estimated seconds left, or None until there is enough data to say anything useful."""
        f = self.fraction
        elapsed = self._clock() - self._t0
        if self.finished:
            return 0.0
        if f < 0.05 or elapsed < 3.0:
            return None
        return max(0.0, elapsed * (1 - f) / f)

    def snapshot(self) -> dict:
        f = self.fraction
        tps = self.tokens_per_second()
        eta = self.eta_seconds()
        return {
            "event": "progress",
            "pct": round(f * 100, 1),
            "chunk": max(1, self.index + 1),
            "chunks": len(self.weights),
            "phase": "done" if self.finished else self.phase,
            "tokens_per_s": round(tps, 1) if tps else None,
            "eta_s": round(eta) if eta is not None else None,
        }
