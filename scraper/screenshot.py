"""Screenshot helper for scraper debugging and evidence."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

EVIDENCE_DIR = Path(".sisyphus/evidence/scraper")


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower() or "screenshot"


async def save_screenshot(page: Page, label: str, evidence_dir: Path | None = None) -> Path:
    """Save a screenshot to .sisyphus/evidence/scraper/ with timestamp prefix."""
    out_dir = evidence_dir or EVIDENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{ts}-{_slug(label)}.png"
    await page.screenshot(path=str(path), full_page=True)
    return path
