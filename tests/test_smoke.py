"""Smoke tests proving pytest infrastructure works."""
from __future__ import annotations

import asyncio
import sys


def test_python_version() -> None:
    """Python 3.11+ required."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version_info}"


async def test_event_loop_runs() -> None:
    """Async tests run without explicit @pytest.mark.asyncio (asyncio_mode=auto)."""
    await asyncio.sleep(0)
    assert True
