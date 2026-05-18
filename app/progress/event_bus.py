"""In-memory SSE event bus.

Per-job asyncio.Queue pubsub. Single subscriber per job.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from time import monotonic

from app.schemas.dto import ProgressEvent

# Sentinel to signal end-of-stream
_SENTINEL: object = object()

# Auto-cleanup window for stale queues (1 hour)
_STALE_AFTER_SECONDS = 3600


class EventBus:
    """In-memory pubsub keyed by job_id."""

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[ProgressEvent | object]] = {}
        self._last_seen: dict[int, float] = {}

    def _get_queue(self, job_id: int) -> asyncio.Queue[ProgressEvent | object]:
        self._cleanup_stale()
        if job_id not in self._queues:
            self._queues[job_id] = asyncio.Queue()
        self._last_seen[job_id] = monotonic()
        return self._queues[job_id]

    def _cleanup_stale(self) -> None:
        now = monotonic()
        stale = [
            jid for jid, ts in self._last_seen.items()
            if now - ts > _STALE_AFTER_SECONDS
        ]
        for jid in stale:
            self._queues.pop(jid, None)
            self._last_seen.pop(jid, None)

    async def publish(self, job_id: int, event: ProgressEvent) -> None:
        queue = self._get_queue(job_id)
        await queue.put(event)

    async def close(self, job_id: int) -> None:
        """Send sentinel and clean up after delivery."""
        if job_id in self._queues:
            await self._queues[job_id].put(_SENTINEL)

    async def subscribe(self, job_id: int) -> AsyncIterator[ProgressEvent]:
        queue = self._get_queue(job_id)
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    return
                assert isinstance(item, ProgressEvent)
                yield item
        finally:
            # Cleanup the queue when subscriber exits
            self._queues.pop(job_id, None)
            self._last_seen.pop(job_id, None)


# Module-level singleton
event_bus = EventBus()
