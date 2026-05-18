"""EMR site discovery script - captures fixtures and selectors.

Run: & .venv\\Scripts\\python.exe discovery\\capture_flow.py

Captures HTML + PNG snapshots at each step of the EMR flow, then anonymizes
patient data before saving to tests/fixtures/emr/.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, TimeoutError as PwTimeout

load_dotenv()

EMR_BASE_URL = os.environ["EMR_BASE_URL"]
EMR_USERNAME = os.environ["EMR_USERNAME"]
EMR_PASSWORD = os.environ["EMR_PASSWORD"]
EMR_PUSKESMAS = os.environ["EMR_PUSKESMAS"]

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "emr"
FIXTURES.mkdir(parents=True, exist_ok=True)

# Discovery report accumulator
REPORT: dict[str, object] = {}

# Known selectors from first discovery run
SELECTORS = {
    "login": {
        "puskesmas_select": "select[name='id_cabang']",
        "puskesmas_value": "16",  # PUSKESMAS BARUHARJO
        "username_input": "input[name='user']",
        "password_input": "input[name='pass']",
        "submit_button": "input[name='submit'][value='Login']",
        "csrf_token": "input[name='csrf_token_name']",
        "login_hidden": "input[name='login']",
        "form": "form[name='form']",
    }
}


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
    # Replace YYYY-MM-DD dates in table contexts
    out = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "1990-01-01", out)
    return out


async def save_snapshot(page: Page, label: str) -> None:
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
            slow_mo=300,
            executable_path=chrome_path,
        )
        context = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await context.new_page()

        # ============================================================
        # STEP 1: Login page
        # ============================================================
        print(f"\n[STEP 1] Navigating to {EMR_BASE_URL}")
        await page.goto(EMR_BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await save_snapshot(page, "01-login")

        # Log form structure for report
        form_info = await page.evaluate("""() => {
            const form = document.querySelector('form[name="form"]');
            if (!form) return {found: false};
            const inputs = Array.from(form.querySelectorAll('input, select')).map(el => ({
                tag: el.tagName, name: el.name, type: el.type, id: el.id, classes: el.className
            }));
            return {found: true, action: form.action, method: form.method, inputs};
        }""")
        print(f"  [INFO] Login form: {json.dumps(form_info, indent=2)}")
        REPORT["login_form"] = form_info

        # ============================================================
        # STEP 2: Fill login form using native select (bypass Select2)
        # ============================================================
        print("\n[STEP 2] Filling login form...")

        # Select puskesmas via native <select> (Select2 wraps it but native still works)
        select_el = page.locator("select[name='id_cabang']")
        await select_el.select_option(value="16")
        await page.wait_for_timeout(500)
        print("  -> Puskesmas selected: value=16 (PUSKESMAS BARUHARJO)")

        # Fill username
        await page.locator("input[name='user']").fill(EMR_USERNAME)
        print(f"  -> Username filled")

        # Fill password
        await page.locator("input[name='pass']").fill(EMR_PASSWORD)
        print(f"  -> Password filled")

        # Click login submit
        print("  -> Submitting login...")
        async with page.expect_navigation(wait_until="networkidle", timeout=15000):
            await page.locator("input[name='submit'][value='Login']").click()

        await page.wait_for_timeout(2000)
        current_url = page.url
        print(f"  -> Post-login URL: {current_url}")
        REPORT["post_login_url"] = current_url

        # Check if login succeeded (page should change or show different content)
        page_title = await page.title()
        print(f"  -> Page title: {page_title}")
        REPORT["post_login_title"] = page_title

        # Check if login form is still visible (means login failed)
        login_form_still = await page.locator("form[name='form']").count()
        if login_form_still > 0:
            # Check for error messages
            error_msg = await page.evaluate("""() => {
                const alerts = document.querySelectorAll('.alert, .error, .warning, [class*=alert]');
                return Array.from(alerts).map(a => a.textContent.trim()).join(' | ');
            }""")
            print(f"  [WARN] Login form still visible! Error: {error_msg or 'none detected'}")
            REPORT["login_error"] = error_msg or "form still visible, no error message"
        else:
            print("  -> Login successful (form no longer visible)")
            REPORT["login_success"] = True

        # ============================================================
        # STEP 3: Capture post-login state
        # ============================================================
        print("\n[STEP 3] Capturing post-login state...")
        await save_snapshot(page, "02-after-login")

        # Detect navigation/menu structure
        nav_info = await page.evaluate("""() => {
            // Look for all links on the page
            const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({
                text: a.textContent.trim().substring(0, 50),
                href: a.href,
                classes: a.className
            })).filter(l => l.text.length > 0 && !l.href.includes('javascript:'));
            return links.slice(0, 30);
        }""")
        print(f"  [INFO] Page links: {json.dumps(nav_info, indent=2, ensure_ascii=False)}")
        REPORT["post_login_links"] = nav_info

        # Look for menu/sidebar
        menu_html = await page.evaluate("""() => {
            const sidebar = document.querySelector('.sidebar, .nav-menu, .menu, nav ul, .navbar-nav');
            if (sidebar) return sidebar.outerHTML.substring(0, 3000);
            // Try to find any list of links
            const lists = document.querySelectorAll('ul');
            for (const ul of lists) {
                const links = ul.querySelectorAll('a');
                if (links.length > 3) return ul.outerHTML.substring(0, 3000);
            }
            return null;
        }""")
        REPORT["menu_html"] = menu_html
        if menu_html:
            print(f"  [INFO] Menu HTML found ({len(menu_html)} chars)")

        # ============================================================
        # STEP 4: Navigate to pendaftaran induk page
        # ============================================================
        print("\n[STEP 4] Navigating to pendaftaran induk...")

        # Try finding the link - from first run we know there's a:has-text('PENDAFTARAN')
        # But the URL pattern should be /daf/px/1/1/0/0
        # Let's try direct navigation first since the link might just reload same page
        target_url = "https://emrtrenggalek.my.id/daf/px/1/1/0/0"

        # First check if there's a specific link
        pendaftaran_links = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links
                .filter(a => a.textContent.includes('PENDAFTARAN') || a.href.includes('/px/'))
                .map(a => ({text: a.textContent.trim(), href: a.href, classes: a.className}));
        }""")
        print(f"  [INFO] Pendaftaran links: {json.dumps(pendaftaran_links, indent=2)}")
        REPORT["pendaftaran_links"] = pendaftaran_links

        if pendaftaran_links:
            # Use the first matching link
            link_href = pendaftaran_links[0].get("href", "")
            if link_href and "/px/" in link_href:
                target_url = link_href
                print(f"  -> Found link with href: {target_url}")

        # Navigate to pendaftaran page
        print(f"  -> Navigating to: {target_url}")
        await page.goto(target_url, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        print(f"  -> Current URL: {page.url}")
        REPORT["pendaftaran_url"] = page.url

        # ============================================================
        # STEP 5: Capture and analyze pendaftaran induk page
        # ============================================================
        print("\n[STEP 5] Capturing pendaftaran induk page...")
        await save_snapshot(page, "03-pendaftaran-induk")

        # Analyze page structure
        page_structure = await page.evaluate("""() => {
            const result = {};

            // Find all forms
            const forms = document.querySelectorAll('form');
            result.forms = Array.from(forms).map(f => ({
                action: f.action, method: f.method, name: f.name,
                inputs: Array.from(f.querySelectorAll('input, select')).map(el => ({
                    tag: el.tagName, name: el.name, type: el.type, id: el.id,
                    classes: el.className, placeholder: el.placeholder || ''
                }))
            }));

            // Find all tables
            const tables = document.querySelectorAll('table');
            result.tables = Array.from(tables).map(t => {
                const headers = Array.from(t.querySelectorAll('th')).map(th => th.textContent.trim());
                const rows = t.querySelectorAll('tbody tr');
                const firstRowCells = rows.length > 0
                    ? Array.from(rows[0].querySelectorAll('td')).map(td => td.textContent.trim().substring(0, 80))
                    : [];
                return {
                    id: t.id, classes: t.className, headers, rowCount: rows.length,
                    firstRowCells, hasLinks: t.querySelectorAll('a').length > 0
                };
            });

            // Find Select2 containers
            result.select2Count = document.querySelectorAll('.select2-container').length;

            // Find date inputs
            result.dateInputs = Array.from(document.querySelectorAll('input[type="date"], input[name*="tgl"], input[name*="tanggal"], .datepicker')).map(el => ({
                tag: el.tagName, name: el.name, type: el.type, id: el.id, value: el.value, classes: el.className
            }));

            // Find pagination
            result.pagination = document.querySelector('.pagination, .dataTables_paginate, [class*=pagina]') !== null;
            const pageLinks = document.querySelectorAll('.pagination a, .paginate_button');
            result.paginationLinks = Array.from(pageLinks).map(a => ({text: a.textContent.trim(), href: a.href || ''})).slice(0, 10);

            // Page title
            result.title = document.title;
            result.h1 = document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : null;

            return result;
        }""")
        print(f"\n  [INFO] Page structure:\n{json.dumps(page_structure, indent=2, ensure_ascii=False)}")
        REPORT["pendaftaran_page_structure"] = page_structure

        # ============================================================
        # STEP 6: Click first patient row to see detail behavior
        # ============================================================
        print("\n[STEP 6] Looking for patient rows to click...")

        # Find clickable elements in the table
        table_links = await page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                const links = table.querySelectorAll('tbody tr a, tbody tr td a');
                if (links.length > 0) {
                    return Array.from(links).slice(0, 5).map(a => ({
                        text: a.textContent.trim().substring(0, 50),
                        href: a.href,
                        onclick: a.getAttribute('onclick') || '',
                        classes: a.className,
                        parentRow: a.closest('tr') ? a.closest('tr').textContent.trim().substring(0, 100) : ''
                    }));
                }
            }
            // Check for clickable rows
            const rows = document.querySelectorAll('table tbody tr[onclick], table tbody tr[style*=cursor]');
            if (rows.length > 0) {
                return Array.from(rows).slice(0, 3).map(r => ({
                    type: 'clickable_row',
                    onclick: r.getAttribute('onclick') || '',
                    text: r.textContent.trim().substring(0, 100)
                }));
            }
            return [];
        }""")
        print(f"  [INFO] Table links/rows: {json.dumps(table_links, indent=2, ensure_ascii=False)}")
        REPORT["table_links"] = table_links

        if table_links:
            # Click the first link/row
            first_link = table_links[0]
            pre_click_url = page.url

            if first_link.get("href") and first_link["href"] != "#":
                print(f"  -> Clicking link: {first_link['href']}")
                await page.locator(f"table tbody a[href='{first_link['href']}']").first.click()
            elif first_link.get("onclick"):
                print(f"  -> Row has onclick: {first_link['onclick']}")
                await page.locator("table tbody tr").first.click()
            else:
                # Try clicking first link in table
                await page.locator("table tbody a").first.click()
                print("  -> Clicked first table link")

            await page.wait_for_timeout(2000)
            post_click_url = page.url
            print(f"  -> URL after click: {post_click_url}")

            # Detect modal
            modal_visible = await page.evaluate("""() => {
                const modals = document.querySelectorAll('.modal.show, .modal.in, .modal[style*="display: block"], [role="dialog"]:not([style*="display: none"])');
                if (modals.length > 0) {
                    return {type: 'modal', selector: modals[0].className, html: modals[0].outerHTML.substring(0, 3000)};
                }
                return null;
            }""")

            if modal_visible:
                REPORT["detail_type"] = "modal"
                REPORT["detail_modal_info"] = modal_visible
                print(f"  -> MODAL detected: {modal_visible['selector']}")
            elif post_click_url != pre_click_url:
                REPORT["detail_type"] = "new_page"
                REPORT["detail_url"] = post_click_url
                print(f"  -> NEW PAGE: {post_click_url}")
            else:
                REPORT["detail_type"] = "unknown_or_inline"
                print("  -> No modal, no URL change")

                # Check if content changed (inline expansion)
                new_elements = await page.evaluate("""() => {
                    const expanded = document.querySelectorAll('.collapse.show, .expanded, [style*="display: block"]');
                    return expanded.length;
                }""")
                if new_elements > 0:
                    REPORT["detail_type"] = "inline_expansion"
                    print(f"  -> Inline expansion detected ({new_elements} elements)")
        else:
            print("  [WARN] No clickable patient rows found")
            REPORT["patient_row_error"] = "no clickable rows in table"

        # ============================================================
        # STEP 7: Capture detail page/modal
        # ============================================================
        print("\n[STEP 7] Capturing detail state...")
        await save_snapshot(page, "04-detail-page-or-modal")

        # Analyze detail content
        detail_structure = await page.evaluate("""() => {
            const result = {};

            // Find tables (tindakan, biaya)
            const tables = document.querySelectorAll('table');
            result.tables = Array.from(tables).map(t => {
                const headers = Array.from(t.querySelectorAll('th')).map(th => th.textContent.trim());
                const rows = t.querySelectorAll('tbody tr');
                return {
                    id: t.id, classes: t.className, headers, rowCount: rows.length
                };
            });

            // Look for biaya/tarif text
            const allText = document.body.innerText;
            result.hasBiaya = allText.includes('Biaya') || allText.includes('biaya');
            result.hasTarif = allText.includes('Tarif') || allText.includes('tarif');
            result.hasTindakan = allText.includes('Tindakan') || allText.includes('tindakan');
            result.hasTotal = allText.includes('Total') || allText.includes('total');

            // Find close/back buttons
            result.closeButtons = Array.from(document.querySelectorAll('.close, .btn-close, [aria-label="Close"], button:has(.fa-times)')).map(b => ({
                tag: b.tagName, classes: b.className, text: b.textContent.trim().substring(0, 30)
            }));
            result.backLinks = Array.from(document.querySelectorAll('a')).filter(a =>
                a.textContent.includes('Kembali') || a.textContent.includes('Back') || a.textContent.includes('←')
            ).map(a => ({text: a.textContent.trim(), href: a.href}));

            return result;
        }""")
        print(f"\n  [INFO] Detail structure:\n{json.dumps(detail_structure, indent=2, ensure_ascii=False)}")
        REPORT["detail_structure"] = detail_structure

        # ============================================================
        # DONE
        # ============================================================
        print("\n[DONE] Discovery complete!")
        print(f"  Fixtures saved to: {FIXTURES}")

        # Save raw report as JSON
        report_path = ROOT / "discovery" / "report.json"
        report_path.write_text(json.dumps(REPORT, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"  Report saved to: {report_path}")

        # Keep browser open for visual inspection
        print("\n  Keeping browser open for 5s...")
        await page.wait_for_timeout(5000)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
