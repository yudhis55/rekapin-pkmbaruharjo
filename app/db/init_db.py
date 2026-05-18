"""Database initialization (idempotent table creation)."""
from __future__ import annotations

from app.db.session import get_engine
from models import Base


async def init_db() -> None:
    """Create all tables if they don't exist."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
