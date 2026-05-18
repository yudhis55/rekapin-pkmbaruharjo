"""Reset database - drops and recreates all tables.

Run: & .venv\\Scripts\\python.exe discovery\\reset_db.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to Python path so 'app' module is found
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def reset_db() -> None:
    db_path = ROOT / "rekap_in.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted {db_path}")

    from app.db.init_db import init_db
    await init_db()
    print("Database reset complete - new schema created")


if __name__ == "__main__":
    asyncio.run(reset_db())
