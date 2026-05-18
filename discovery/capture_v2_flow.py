"""
v2 EMR Discovery Script
Captures: pagination page 2, payment page (halaman bayar)
Run: & .venv\Scripts\python.exe discovery\capture_v2_flow.py
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv()

EMR_BASE_URL = os.environ["EMR_BASE_URL"]
EMR_USERNAME = os.environ["EMR_USERNAME"]
EMR_PASSWORD = os.environ["EMR_PASSWORD"]
EMR_PUSKESMAS = os.environ["EMR_PUSKESMAS"]

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "emr"
FIXTURES.mkdir(parents=True, exist_ok=True)


def anonymize_html(html: str) -> str:
    """Strip likely PII before saving fixture."""
    counter = {"n": 0}

    def _replace_id(m: re.Match[str]) -> str:
        counter["n"] += 1
        return f"PATIENT_{counter['n']:03d}"

    # Replace 6+ digit sequences (RM/NIK numbers)
    out = re.sub(r"\b\d{6,}\b", _replace_id, html)
    # Replace dates DD/MM/YYYY or DD-MM-YYYY with sample date
    out = re.sub(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", "01/01/1990", out)
    # Replace YYYY-MM-DD dates
    out = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "1990-01-01", out)
    return out


async def save_fixture(page: Page, label: str) -> None:
    """Save anonymized HTML + PNG screenshot."""
    html = await page.content()
    anon = anonymize_html(html)
    (FIXTURES / f"{label}.html").write_text(anon, encoding="utf-8")
    await page.screenshot(path=str(FIXTURES / f"{label}.png"), full_page=True)
    print(f"  [OK] saved {label}.html + .png")


async def main() -> None:
    chrome_path = r"C:\Users\Yudhistira\AppData\Local\ms-playwright\chromium-1169\chrome-win\chrome.exe"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=500,
            executable_path=chrome_path,
        )
        context = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await context.new_page()

        # ============================================================
        # STEP 1: Login
        # ============================================================
        print(f"\n[STEP 1] Navigating to {EMR_BASE_URL}")
        await page.goto(EMR_BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Select puskesmas via native <select>
        await page.locator("select[name='id_cabang']").select_option(value="16")
        await page.wait_for_timeout(500)
        await page.locator("input[name='user']").fill(EMR_USERNAME)
        await page.locator("input[name='pass']").fill(EMR_PASSWORD)

        print("[STEP 2] Submitting login...")
        async with page.expect_navigation(wait_until="networkidle", timeout=15000):
            await page.locator("input[name='submit'][value='Login']").click()
        await page.wait_for_timeout(2000)
        print(f"  -> Post-login URL: {page.url}")

        # ============================================================
        # STEP 3: Navigate to PENDAFTARAN INDUK
        # ============================================================
        print("[STEP 3] Navigating to PENDAFTARAN INDUK...")
        await page.locator("a[href*='/daf/px/1/1/0/0']").click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        print(f"  -> URL: {page.url}")

        # ============================================================
        # STEP 4: Set date filter (today) and search
        # ============================================================
        from datetime import date

        today = date.today().strftime("%Y-%m-%d")
        print(f"[STEP 4] Setting date filter to {today}...")
        await page.locator("input[name='tanggal'][type='date']").fill(today)
        await page.locator("button[title='cari']").click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        # ============================================================
        # STEP 5: Check pagination
        # ============================================================
        print("[STEP 5] Checking pagination...")
        pagination_text = None
        try:
            pagination_el = page.locator(
                "table[align='left'][width='25%'] td:nth-child(3)"
            )
            if await pagination_el.count() > 0:
                pagination_text = (await pagination_el.first.inner_text()).strip()
                print(f"  -> Pagination indicator: '{pagination_text}'")
        except Exception as e:
            print(f"  -> Pagination check error: {e}")

        # ============================================================
        # STEP 6: Navigate to page 2 if multiple pages exist
        # ============================================================
        if pagination_text and "/" in pagination_text:
            current, total = pagination_text.split("/")
            if int(total.strip()) > 1:
                print(f"[STEP 6] Navigating to page 2 (currently {current}/{total})...")
                # Next button form has .fa-forward but NOT .fa-fast-forward
                next_form = page.locator(
                    "table[align='left'][width='25%'] form:has(.fa-forward):not(:has(.fa-fast-forward))"
                )
                if await next_form.count() > 0:
                    # Submit the form via JS
                    await next_form.first.evaluate("form => form.submit()")
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(1000)
                    await save_fixture(page, "05-pagination-page2")
                    print("  -> Saved 05-pagination-page2")

                    # Go back to page 1
                    first_form = page.locator(
                        "table[align='left'][width='25%'] form:has(.fa-fast-backward)"
                    )
                    if await first_form.count() > 0:
                        await first_form.first.evaluate("form => form.submit()")
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(1000)
                        print("  -> Back to page 1")
                else:
                    print("  -> Next form not found, skipping page 2 capture")
        else:
            print("[STEP 6] No pagination or single page, skipping page 2 capture")

        # ============================================================
        # STEP 7: Find a Bayar button and click it
        # ============================================================
        print("[STEP 7] Looking for Bayar button...")
        bayar_forms = page.locator("form[action*='/daf/px/20/1/']")
        bayar_count = await bayar_forms.count()
        print(f"  -> Found {bayar_count} Bayar forms")

        if bayar_count > 0:
            # Get action URL for logging
            action = await bayar_forms.first.get_attribute("action")
            print(f"  -> First Bayar form action: {action}")

            # Click the button inside the first Bayar form
            bayar_btn = bayar_forms.first.locator("button")
            if await bayar_btn.count() > 0:
                await bayar_btn.first.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                print(f"  -> Payment page URL: {page.url}")

                # Save payment page fixture
                await save_fixture(page, "06-payment-page")

                # Inspect page structure
                tables = page.locator("table")
                table_count = await tables.count()
                print(f"  -> Tables on payment page: {table_count}")
                for i in range(min(table_count, 8)):
                    text = (await tables.nth(i).inner_text())[:120].replace("\n", " ")
                    print(f"     Table {i}: {text}")

                # Look for Selesai button
                selesai = page.locator(
                    "input[type='submit'][value='Selesai'], button:has-text('Selesai')"
                )
                if await selesai.count() > 0:
                    print("[STEP 8] Found Selesai button, clicking...")
                    await selesai.first.click()
                    await page.wait_for_load_state("networkidle")
                    print(f"  -> Back to: {page.url}")
                else:
                    print("[STEP 8] Selesai button not found! Listing all buttons:")
                    btns = page.locator("button, input[type='submit']")
                    btn_count = await btns.count()
                    for i in range(btn_count):
                        btn = btns.nth(i)
                        tag = await btn.evaluate("el => el.tagName")
                        if tag == "INPUT":
                            txt = await btn.get_attribute("value") or ""
                        else:
                            txt = (await btn.inner_text())[:50]
                        print(f"     Button {i}: [{tag}] {txt}")
        else:
            print("  -> No Bayar forms found on this page")

        # ============================================================
        # DONE
        # ============================================================
        print("\n[DONE] v2 Discovery complete")
        await page.wait_for_timeout(3000)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
