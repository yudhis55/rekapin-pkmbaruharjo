"""Tests for in-memory SSE event bus."""
from __future__ import annotations

import asyncio

import pytest

from app.progress.event_bus import EventBus
from app.schemas.dto import ProgressEvent


async def test_publish_then_subscribe_yields_event() -> None:
    bus = EventBus()
    job_id = 1
    ev = ProgressEvent(event_type="log", message="hello")

    async def consumer() -> ProgressEvent:
        async for e in bus.subscribe(job_id):
            return e
        raise AssertionError("no event received")

    consume_task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)  # let subscriber attach
    await bus.publish(job_id, ev)
    await bus.close(job_id)

    received = await asyncio.wait_for(consume_task, timeout=2.0)
    assert received.event_type == "log"
    assert received.message == "hello"


async def test_close_terminates_subscription() -> None:
    bus = EventBus()
    job_id = 2

    async def consumer() -> int:
        count = 0
        async for _ in bus.subscribe(job_id):
            count += 1
        return count

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)
    await bus.publish(job_id, ProgressEvent(event_type="log", message="x"))
    await bus.publish(job_id, ProgressEvent(event_type="log", message="y"))
    await bus.close(job_id)

    count = await asyncio.wait_for(task, timeout=2.0)
    assert count == 2


async def test_unknown_job_subscribe_creates_queue() -> None:
    """Subscribing to a job_id with no published events yet still works."""
    bus = EventBus()
    job_id = 999

    async def consumer() -> ProgressEvent | None:
        async for e in bus.subscribe(job_id):
            return e
        return None

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)
    await bus.publish(job_id, ProgressEvent(event_type="done", message="finished"))
    await bus.close(job_id)
    received = await asyncio.wait_for(task, timeout=2.0)
    assert received is not None
    assert received.event_type == "done"


async def test_module_singleton_is_instance() -> None:
    from app.progress.event_bus import event_bus
    assert isinstance(event_bus, EventBus)
