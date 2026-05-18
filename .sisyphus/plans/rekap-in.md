# Rekap-In: EMR Scraping Web App

## TL;DR

> **Quick Summary**: Build a Python web application that scrapes patient + treatment + cost data from EMR Trenggalek (`https://emrtrenggalek.my.id/daf` for PUSKESMAS BARUHARJO), displays it in a Tailwind UI, and tracks daily recap totals with SQLite history.
>
> **Deliverables**:
> - FastAPI web app (localhost) with Jinja2 + Tailwind UI
> - Playwright async scraper (login → select puskesmas → pendaftaran induk → loop click rows → extract details)
> - Date filter (single/range), ruang dropdown, real-time SSE progress
> - Patient table + per-date recap history with totals
> - Selector config (externalized for resilience)
> - TDD: pytest suite for pure logic, HTML fixtures for scraper unit tests
>
> **Estimated Effort**: Large (≈22 implementation tasks + 4 verification)
> **Parallel Execution**: YES - 3 implementation waves + final verification wave
> **Critical Path**: Task 1 (scaffold) → Task 5 (DB models) → Task 9 (scraper core) → Task 11 (scraper integration) → Task 17 (main route + SSE) → Task 22 (e2e wiring) → F1-F4

---

## Context

### Original Request
User wants a Python scraping project for EMR Trenggalek that extracts patient data (identity, ruang, treatments, costs) for PUSKESMAS BARUHARJO. The scraper goes through login → select puskesmas → fill credentials (from `.env`) → click "PENDAFTARAN INDUK" → land on `/px/1/1/0/0` → extract data per patient. UI must be modern Tailwind with date/ruang filters, results table, history of daily recaps. Excel export was requested but **deferred to v2** (template not yet available).

### Interview Summary

**Key Decisions**:
- **Tech stack**: FastAPI + Jinja2 + Tailwind (server-side render, single Python repo)
- **Scraping**: Playwright async (handles Select2, JS-heavy EMR), headless default with env toggle for visible debug
- **Storage**: SQLite + SQLAlchemy 2.x async
- **Filter strategy**: Filter at EMR source (form parameters), not post-process
- **Detail strategy**: Loop-click each row sequentially → extract treatment + cost → return → next
- **Date input**: Single date OR date range (UI toggle)
- **Ruang list**: Hardcoded in `config/ruang.py` with placeholders (Poli Umum, Poli Gigi, KIA, KB, Imunisasi, Lab, Apotek, IGD, Pendaftaran)
- **Progress feedback**: Server-Sent Events (real-time)
- **History granularity**: Per visit-date (1 record = 1 day, re-scrape updates)
- **Test approach**: TDD with pytest + pytest-asyncio (RED → GREEN → REFACTOR)
- **Excel export**: DEFERRED to v2 (placeholder button, disabled in v1)

**Research Findings**:
- Could not explore live EMR (requires login). All selectors will be discovered by Sisyphus during execution and must be externalized into a YAML/JSON config for resilience (per Metis review).

### Metis Review

**Identified Gaps** (addressed in this plan):
- **EMR row-click behavior unknown**: Plan includes early discovery task (Task 7) that documents actual behavior (modal vs navigation vs inline) BEFORE building loop logic. Scraper architecture supports all 3 modes via strategy pattern.
- **Session timeout risk**: Scraper detects re-direct to login URL → triggers re-login → resumes. Session validity check before each row click.
- **Selector fragility**: All selectors in `config/selectors.yaml` (not hardcoded). Failure = clear error with page screenshot saved for debugging.
- **Anti-bot risk**: Sequential clicks with humanized delay (300-800ms jitter). No parallelism. Failed selector = abort cleanly with diagnostics.
- **Medical data privacy**: No PII in logs. SQLite encrypted at rest is OUT OF SCOPE for v1 (single-user local app), but logs MUST redact names/RM numbers.
- **Pagination**: Plan auto-detects pagination on `/px/1/1/0/0` and loops if present.
- **Multiple visits same day**: Captured as separate rows, deduplicated by (no_rm, ruang, tanggal_kunjungan, tindakan_hash).
- **User cancellation**: Cancel button stops scraper gracefully, persists partial results with `status=cancelled`.
- **Concurrent triggers**: Server enforces single-active-job lock (in-memory + DB flag).

---

## Work Objectives

### Core Objective
Deliver a working local web app where a Puskesmas Baruharjo staff can: open `http://localhost:8000` → choose date(s) and ruang → click scrape → watch real-time progress → see patient table populated → see per-date recap appear in history. All without manually opening the EMR site.

### Concrete Deliverables
- `app/` FastAPI application package
- `scraper/` Playwright async scraper package
- `models/` SQLAlchemy models (PatientVisit, Treatment, ScrapeJob, DailyRecap)
- `config/` settings + ruang list + selectors YAML
- `templates/` Jinja2 templates (index, partials)
- `static/` Tailwind compiled CSS + minimal JS
- `tests/` pytest suite (unit + scraper-with-fixtures)
- `.env.example` + `.gitignore` + `requirements.txt` + `README.md`
- One-line start: `python -m app` (loads .env, runs uvicorn)

### Definition of Done
- [ ] User runs `pip install -r requirements.txt && playwright install chromium && python -m app` and the UI loads at `http://127.0.0.1:8000`
- [ ] User fills `.env`, picks a date + ruang, clicks scrape, sees progress events stream live, sees patient table after completion
- [ ] History section shows per-date recap with total Rp and last-scraped timestamp
- [ ] Re-scraping the same date UPDATES the existing recap record (not duplicates)
- [ ] All pytest unit tests pass (`pytest tests/ -v`)
- [ ] Final verification wave (F1-F4) all APPROVE

### Must Have
- Login flow (Select2 + credentials + login button) using selectors from config
- Click "PENDAFTARAN INDUK" → navigate to `/px/1/1/0/0`
- Apply date filter (single + range) and ruang filter at EMR
- Loop click each patient row, extract: No RM, Nama, Tgl Lahir, Ruang, Tindakan, Biaya, Tanggal Kunjungan
- Persist to SQLite with proper foreign keys (PatientVisit → Treatment 1:N)
- Real-time SSE progress feed
- Per-date recap (1 record = 1 visit-date, upsert on re-scrape)
- Tailwind UI with date toggle (single/range) + ruang dropdown + table + history
- Cancel button that stops scrape gracefully
- TDD: tests written BEFORE implementation per task

### Must NOT Have (Guardrails)
- ❌ NO Excel export logic in v1 (placeholder disabled button only)
- ❌ NO multi-user authentication (single-user local app)
- ❌ NO multi-puskesmas (locked to BARUHARJO via env)
- ❌ NO cloud deployment, no Docker (local-only v1)
- ❌ NO mobile responsive (desktop-first MVP)
- ❌ NO real EMR integration test in CI (mocked HTML fixtures only)
- ❌ NO over-abstraction: avoid generic names like `data`, `result`, `item`, `temp`, `helper`, `manager`, `service` without domain prefix
- ❌ NO premature `BaseScraper`/`AbstractStorage` abstractions until needed twice
- ❌ NO PII in logs (redact No RM, Nama before logging)
- ❌ NO `as Any` / `# type: ignore` to silence type errors without justification comment
- ❌ NO commented-out code in committed files
- ❌ NO `console.log`, `print()`, `debugger` left in production code (use `logging` module)
- ❌ NO selectors hardcoded inline (must live in `config/selectors.yaml`)
- ❌ NO Playwright `time.sleep(N)` long sleeps (use `wait_for_selector` / `wait_for_load_state`)
- ❌ NO synchronous `requests` calls (entire stack is async)
- ❌ NO over-engineered error handling (15 try/except for 3 inputs); meaningful errors only
- ❌ NO premature scheduler/cron logic (manual trigger only in v1)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - All verification is agent-executed. No "user manually tests" criteria allowed.

### Test Decision
- **Infrastructure exists**: NO (greenfield) - Task 2 sets up pytest
- **Automated tests**: YES (TDD)
- **Framework**: pytest + pytest-asyncio + pytest-playwright (for fixtures only)
- **TDD pattern**: Each implementation task includes (a) failing tests written first (RED), (b) minimal impl to pass (GREEN), (c) cleanup (REFACTOR)

### QA Policy
Every task includes Agent-Executed QA Scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{slug}.{ext}`.

- **Frontend/UI tasks**: Playwright (via `playwright` skill) - launch browser, navigate to localhost, interact, assert DOM, screenshot
- **Backend/API tasks**: `curl` via Bash - hit endpoints, assert JSON response + status
- **Scraper tasks**: pytest with HTML fixture (no real EMR), agent runs `pytest tests/scraper/ -v` and captures output
- **Database tasks**: agent uses `sqlite3` CLI to query DB, asserts rows
- **SSE tasks**: agent uses `curl --no-buffer` + Python SSE client to assert event stream

### Test Data Strategy
- HTML fixtures in `tests/fixtures/emr/` (saved snapshots of expected pages)
- Sisyphus discovers actual selectors during scraper task → saves anonymized fixtures
- Synthetic patient data: 3 sample patients with 1, 2, 3 treatments respectively (covers single-treatment + multi-treatment edge cases)

---

## Execution Strategy

### Parallel Execution Waves

> Target: 5-8 tasks per wave. Foundation tasks first (extracted dependencies), then parallel modules, then integration.

```
Wave 1 (Foundation - all start immediately, max parallel):
├── Task 1: Project scaffolding + config files (.env.example, .gitignore, requirements.txt, pyproject.toml)
├── Task 2: pytest test infrastructure setup
├── Task 3: Tailwind CLI setup + base styles
├── Task 4: Configuration module (env loader + selectors YAML schema)
├── Task 5: SQLAlchemy models (PatientVisit, Treatment, ScrapeJob, DailyRecap)
├── Task 6: Pydantic schemas (request/response DTOs + domain types)
└── Task 7: EMR site discovery + selector documentation

Wave 2 (Core modules - depend on Wave 1):
├── Task 8: Database session + repository layer
├── Task 9: Playwright browser context manager (launch/headless toggle/cleanup)
├── Task 10: Scraper - login flow module (Select2 + credentials + login click)
├── Task 11: Scraper - navigation module (PENDAFTARAN INDUK → /px/1/1/0/0)
├── Task 12: Scraper - filter module (apply date + ruang to EMR form)
├── Task 13: Scraper - row extraction module (table parse + click loop strategy)
├── Task 14: SSE progress event bus (in-memory pubsub)
└── Task 15: Job orchestrator (state machine: pending → running → done/error/cancelled)

Wave 3 (Integration + UI - depend on Wave 2):
├── Task 16: FastAPI app skeleton + middleware + lifespan
├── Task 17: Routes - GET / (index page) + GET /api/ruang
├── Task 18: Routes - POST /api/scrape (trigger) + GET /api/scrape/stream (SSE)
├── Task 19: Routes - GET /api/visits + GET /api/recap (history)
├── Task 20: Jinja2 templates - base + index + partials (form, table, history)
├── Task 21: Frontend JS - SSE consumer + table updater + form interactions
└── Task 22: End-to-end wiring + recap upsert logic

Wave FINAL (4 parallel reviews → user okay):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA via Playwright + curl (unspecified-high)
└── F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|---|---|---|---|
| 1 | - | 2,3,4,5,6,7 | 1 |
| 2 | 1 | All test work | 1 |
| 3 | 1 | 20 | 1 |
| 4 | 1 | 9,10,11,12,13 | 1 |
| 5 | 1 | 8,15,22 | 1 |
| 6 | 1 | 17,18,19 | 1 |
| 7 | 1 | 10,11,12,13 (selectors documented) | 1 |
| 8 | 5 | 15,17,19,22 | 2 |
| 9 | 4 | 10,11,12,13 | 2 |
| 10 | 4,7,9 | 11,15 | 2 |
| 11 | 4,7,9,10 | 12,15 | 2 |
| 12 | 4,7,9,11 | 13,15 | 2 |
| 13 | 4,7,9,12 | 15 | 2 |
| 14 | 6 | 15,18,21 | 2 |
| 15 | 5,8,10,11,12,13,14 | 18,22 | 2 |
| 16 | 8 | 17,18,19 | 3 |
| 17 | 6,8,16 | 20 | 3 |
| 18 | 6,8,14,15,16 | 21 | 3 |
| 19 | 6,8,16 | 20 | 3 |
| 20 | 3,17,19 | 21 | 3 |
| 21 | 14,18,20 | 22 | 3 |
| 22 | 5,8,15,17,18,19,20,21 | F1-F4 | 3 |

### Agent Dispatch Summary

| Wave | Tasks | Agents |
|---|---|---|
| 1 | 7 | T1 → `quick`, T2 → `quick`, T3 → `visual-engineering`, T4 → `quick`, T5 → `unspecified-high`, T6 → `quick`, T7 → `deep` |
| 2 | 8 | T8 → `unspecified-high`, T9 → `unspecified-high`, T10 → `deep`, T11 → `deep`, T12 → `deep`, T13 → `deep`, T14 → `unspecified-high`, T15 → `deep` |
| 3 | 7 | T16 → `quick`, T17 → `unspecified-high`, T18 → `unspecified-high`, T19 → `unspecified-high`, T20 → `visual-engineering`, T21 → `visual-engineering`, T22 → `deep` |
| FINAL | 4 | F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep` |

---

## TODOs

- [x] 1. **Project scaffolding + config files**

  **What to do**:
  - Create directory tree: `app/`, `scraper/`, `models/`, `config/`, `templates/`, `static/`, `tests/`, `.sisyphus/evidence/`, `tests/fixtures/emr/`, `exports/` (placeholder)
  - Create `requirements.txt` with: `fastapi>=0.110`, `uvicorn[standard]>=0.27`, `jinja2>=3.1`, `python-dotenv>=1.0`, `sqlalchemy[asyncio]>=2.0`, `aiosqlite>=0.19`, `playwright>=1.40`, `pyyaml>=6.0`, `pydantic>=2.5`, `sse-starlette>=2.0`
  - Create `requirements-dev.txt` with: `pytest>=8.0`, `pytest-asyncio>=0.23`, `pytest-playwright>=0.4`, `pytest-cov>=4.1`, `ruff>=0.3`, `mypy>=1.8`, `httpx>=0.26` (for testing)
  - Create `pyproject.toml` with `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections (asyncio_mode = "auto")
  - Create `.env.example` with all required vars: `EMR_USERNAME`, `EMR_PASSWORD`, `EMR_BASE_URL=https://emrtrenggalek.my.id/daf`, `EMR_PUSKESMAS=PUSKESMAS BARUHARJO`, `BROWSER_MODE=headless`, `SCRAPE_TIMEOUT=60`, `DATABASE_URL=sqlite+aiosqlite:///./rekap_in.db`, `APP_HOST=127.0.0.1`, `APP_PORT=8000`
  - Create `.env` as a COPY of `.env.example` (user fills credentials manually after this task)
  - Create `.gitignore` with: `.env`, `*.db`, `__pycache__/`, `.venv/`, `venv/`, `*.egg-info/`, `dist/`, `build/`, `playwright-report/`, `test-results/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `static/css/output.css`, `.sisyphus/drafts/`, `exports/*.xlsx`
  - Create `README.md` with quickstart: clone → `pip install -r requirements.txt && pip install -r requirements-dev.txt` → `playwright install chromium` → fill `.env` → `python -m app`
  - Create empty `__init__.py` in: `app/`, `scraper/`, `models/`, `config/`, `tests/`

  **Must NOT do**:
  - Do NOT install packages or run pip commands (Sisyphus runs that as a separate verification step)
  - Do NOT create files in `app/`, `scraper/`, `models/` beyond `__init__.py` (those belong to later tasks)
  - Do NOT pre-create selectors.yaml (Task 4 owns that schema)
  - Do NOT create any .ts/.js/.css files (Task 3 owns frontend)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pure scaffolding, no domain logic, single concern (file/dir creation)
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `git-master`: Initial commit happens in commit step, no special git workflow needed yet

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 foundation - must run FIRST, blocks all other Wave 1 tasks
  - **Blocks**: 2, 3, 4, 5, 6, 7
  - **Blocked By**: None

  **References**:

  **Pattern References**: None (greenfield)

  **External References**:
  - FastAPI quickstart: `https://fastapi.tiangolo.com/tutorial/first-steps/` - confirms minimum dependencies
  - Playwright Python: `https://playwright.dev/python/docs/intro` - install steps for `playwright install chromium`
  - SQLAlchemy 2.x async: `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html` - aiosqlite driver requirement
  - sse-starlette: `https://github.com/sysid/sse-starlette` - SSE for FastAPI

  **WHY Each Reference Matters**:
  - FastAPI docs justify `uvicorn[standard]` extras (uvloop, httptools)
  - Playwright docs explain why `chromium` (not full browser pack) is enough
  - SQLAlchemy async docs require `aiosqlite` driver string `sqlite+aiosqlite:///`
  - sse-starlette is the canonical SSE library for Starlette/FastAPI (avoid hand-rolling SSE)

  **Acceptance Criteria**:
  - [ ] `Test-Path C:\PKM\rekap-in\requirements.txt` returns True
  - [ ] `Test-Path C:\PKM\rekap-in\.env.example` returns True
  - [ ] `Test-Path C:\PKM\rekap-in\.env` returns True
  - [ ] `Test-Path C:\PKM\rekap-in\.gitignore` returns True
  - [ ] `Test-Path C:\PKM\rekap-in\pyproject.toml` returns True
  - [ ] `Test-Path C:\PKM\rekap-in\README.md` returns True
  - [ ] All package `__init__.py` files exist (`app`, `scraper`, `models`, `config`, `tests`)
  - [ ] `Get-Content .gitignore | Select-String "\.env$"` returns a match (`.env` is gitignored)
  - [ ] `Get-Content requirements.txt | Select-String "fastapi"` returns a match
  - [ ] `Get-Content requirements.txt | Select-String "playwright"` returns a match

  **QA Scenarios**:

  ```
  Scenario: All scaffolding files and directories created with correct content
    Tool: Bash (PowerShell)
    Preconditions: Working directory is C:\PKM\rekap-in (only has .sisyphus/ inside)
    Steps:
      1. Run: Get-ChildItem -Force -Recurse -Depth 1 | Select-Object FullName
      2. Assert output contains: requirements.txt, .env, .env.example, .gitignore, pyproject.toml, README.md
      3. Assert output contains directories: app, scraper, models, config, templates, static, tests
      4. Run: Get-Content .env.example -Raw
      5. Assert contains all 9 env vars listed in spec
      6. Run: Get-Content .gitignore -Raw
      7. Assert contains: ".env", "*.db", "__pycache__"
    Expected Result: All files present with required keys; no extra source files yet
    Failure Indicators: Missing required file, missing env var key, .env not gitignored
    Evidence: .sisyphus/evidence/task-1-scaffold-listing.txt

  Scenario: Repository is in clean state ready for next task
    Tool: Bash
    Preconditions: After scaffold creation
    Steps:
      1. Run: Get-ChildItem app, scraper, models, config -Force | Select-Object FullName
      2. Assert each directory contains only __init__.py
    Expected Result: Each package has __init__.py, no premature implementation files
    Failure Indicators: Source code files present in app/, scraper/ etc.
    Evidence: .sisyphus/evidence/task-1-clean-state.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-1-scaffold-listing.txt` (file/dir tree)
  - [ ] `.sisyphus/evidence/task-1-clean-state.txt` (verifies no source code yet)

  **Commit**: YES
  - Message: `chore(scaffold): initial project structure with .env.example and requirements`
  - Files: All scaffold files
  - Pre-commit: `Test-Path requirements.txt, .env.example, .gitignore, pyproject.toml`

- [x] 2. **pytest test infrastructure setup**

  **What to do**:
  - Create `tests/conftest.py` with: `pytest_asyncio` config, `tmp_path` fixtures, `event_loop` fixture for async, `db_session` async fixture using in-memory SQLite (`sqlite+aiosqlite:///:memory:`), `mock_env` fixture that sets test env vars
  - Create `tests/fixtures/__init__.py`
  - Create `tests/fixtures/emr/.gitkeep` (placeholder for HTML fixtures Task 7 will populate)
  - Create `tests/test_smoke.py` with one test: `def test_python_version()` asserts `sys.version_info >= (3, 11)`, and `async def test_event_loop()` asserts asyncio loop runs
  - Update `pyproject.toml`: add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `python_files = "test_*.py"`, `addopts = "-v --tb=short"`
  - Add `[tool.coverage.run]` to `pyproject.toml`: `source = ["app", "scraper", "models", "config"]`, `omit = ["*/tests/*"]`

  **Must NOT do**:
  - Do NOT write actual functionality tests (only smoke tests verifying infrastructure)
  - Do NOT install packages (Sisyphus separately runs `pip install`)
  - Do NOT create test files for modules that don't exist yet (those tests live with their respective tasks)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-concern setup task, well-known pytest configuration patterns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 4, 5, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: All future test work (any task with tests)
  - **Blocked By**: 1

  **References**:

  **External References**:
  - pytest-asyncio docs: `https://pytest-asyncio.readthedocs.io/en/latest/concepts.html` - `asyncio_mode = "auto"` rationale
  - SQLAlchemy testing patterns: `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncio-scoped-session` - in-memory async session

  **WHY Each Reference Matters**:
  - `asyncio_mode = "auto"` lets us write `async def test_*` without `@pytest.mark.asyncio` on every test (DRY)
  - In-memory async session pattern is needed for fast, isolated DB tests in Wave 2

  **Acceptance Criteria**:
  - [ ] `Test-Path tests/conftest.py` returns True
  - [ ] `Test-Path tests/test_smoke.py` returns True
  - [ ] `pytest tests/test_smoke.py -v` exits 0 with 2 passed
  - [ ] `Get-Content pyproject.toml | Select-String "asyncio_mode"` matches

  **QA Scenarios**:

  ```
  Scenario: Smoke test runs successfully proving pytest infrastructure works
    Tool: Bash
    Preconditions: Task 1 done, requirements installed
    Steps:
      1. Run: pytest tests/test_smoke.py -v 2>&1 | Tee-Object .sisyphus/evidence/task-2-smoke-output.txt
      2. Assert exit code is 0
      3. Assert output contains "2 passed"
      4. Assert output contains "test_python_version" and "test_event_loop"
    Expected Result: Both tests pass, pytest configured with asyncio
    Failure Indicators: ImportError, "no tests collected", asyncio errors
    Evidence: .sisyphus/evidence/task-2-smoke-output.txt

  Scenario: Async fixture discovery works with no marker required
    Tool: Bash
    Preconditions: After smoke test
    Steps:
      1. Run: pytest tests/test_smoke.py::test_event_loop -v
      2. Assert "PASSED" appears
    Expected Result: Async test runs without explicit @pytest.mark.asyncio
    Failure Indicators: "async def" warning or test skipped
    Evidence: .sisyphus/evidence/task-2-async-mode.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-2-smoke-output.txt`
  - [ ] `.sisyphus/evidence/task-2-async-mode.txt`

  **Commit**: YES
  - Message: `chore(test): pytest infrastructure with async support`
  - Files: `tests/conftest.py`, `tests/test_smoke.py`, `tests/fixtures/.gitkeep`, `pyproject.toml` (updated)
  - Pre-commit: `pytest tests/test_smoke.py -v`

- [x] 3. **Tailwind CLI setup + base styles**

  **What to do**:
  - Download standalone Tailwind CLI binary (`tailwindcss-windows-x64.exe`) into `tools/` directory (no npm dependency)
  - Create `tailwind.config.js` with `content: ["./templates/**/*.html", "./static/js/**/*.js"]`, theme extend with custom palette (slate primary, emerald accent for medical context, no neon colors)
  - Create `static/css/input.css` with Tailwind directives (`@tailwind base/components/utilities`) plus custom component classes: `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.card`, `.input`, `.label`, `.table-medical`, `.badge`
  - Create build script `tools/build-css.ps1`: runs `./tools/tailwindcss-windows-x64.exe -i static/css/input.css -o static/css/output.css --minify`
  - Add to `README.md`: instructions to download Tailwind CLI, build CSS once, and watch with `--watch` flag
  - Run build once to produce initial `static/css/output.css`

  **Must NOT do**:
  - Do NOT add `package.json` / npm dependencies (we use standalone CLI to keep stack pure-Python)
  - Do NOT inline `<style>` tags in templates
  - Do NOT use Tailwind CDN (production-quality requires built CSS)
  - Do NOT add complex theme tokens beyond medical-appropriate palette

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI tooling + design tokens; needs aesthetic judgment for medical-context palette
  - **Skills**: `[]`
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Possible but the actual UI rendering happens in Tasks 20-21; this task is purely the build pipeline + tokens

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 4, 5, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: 20 (templates need compiled CSS)
  - **Blocked By**: 1

  **References**:

  **External References**:
  - Tailwind standalone: `https://tailwindcss.com/blog/standalone-cli` - rationale for no-Node setup
  - Tailwind config: `https://tailwindcss.com/docs/configuration` - content paths and theme extension
  - Color palette inspiration: `https://tailwindcss.com/docs/customizing-colors` - slate + emerald combo

  **WHY Each Reference Matters**:
  - Standalone CLI eliminates Node.js dependency (matches our pure-Python stack)
  - `content` paths control purging - missing this = bloated 3MB CSS
  - Slate (neutral) + emerald (success/health) is calm and professional, fits medical UX

  **Acceptance Criteria**:
  - [ ] `Test-Path tools/tailwindcss-windows-x64.exe` returns True
  - [ ] `Test-Path tailwind.config.js` returns True
  - [ ] `Test-Path static/css/input.css` returns True
  - [ ] `Test-Path static/css/output.css` returns True
  - [ ] `(Get-Item static/css/output.css).Length -gt 5000` (CSS is non-trivial)
  - [ ] `Get-Content static/css/output.css | Select-String "btn-primary"` matches (custom component compiled)

  **QA Scenarios**:

  ```
  Scenario: Tailwind builds custom + utility classes into output.css
    Tool: Bash (PowerShell)
    Preconditions: Task 1 done; Tailwind binary downloaded
    Steps:
      1. Run: ./tools/build-css.ps1 2>&1 | Tee-Object .sisyphus/evidence/task-3-build.txt
      2. Assert exit code 0
      3. Run: (Get-Item static/css/output.css).Length
      4. Assert size > 5KB and < 200KB (purged correctly)
      5. Run: Get-Content static/css/output.css | Select-String "\.btn-primary"
      6. Assert match found
    Expected Result: output.css generated with custom + Tailwind classes
    Failure Indicators: build fails, output > 1MB (no purge), missing custom classes
    Evidence: .sisyphus/evidence/task-3-build.txt

  Scenario: Build script reproducibly regenerates CSS
    Tool: Bash
    Preconditions: After first build
    Steps:
      1. Run: Remove-Item static/css/output.css
      2. Run: ./tools/build-css.ps1
      3. Assert output.css regenerated with same hash range
    Expected Result: Idempotent build pipeline
    Failure Indicators: Different output between runs without code change
    Evidence: .sisyphus/evidence/task-3-rebuild.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-3-build.txt`
  - [ ] `.sisyphus/evidence/task-3-rebuild.txt`

  **Commit**: YES
  - Message: `chore(ui): tailwind cli setup with base styles`
  - Files: `tailwind.config.js`, `static/css/input.css`, `tools/build-css.ps1`, `README.md` (updated). Note: `tools/tailwindcss-windows-x64.exe` and `static/css/output.css` are gitignored
  - Pre-commit: `Test-Path static/css/output.css`

- [x] 4. **Configuration module (env loader + selectors YAML schema)**

  **What to do**:
  - Create `config/settings.py` with `Settings` Pydantic BaseSettings class loading from `.env`: `emr_username: SecretStr`, `emr_password: SecretStr`, `emr_base_url: str`, `emr_puskesmas: str`, `browser_mode: Literal["headless","visible"]`, `scrape_timeout: int = 60`, `database_url: str`, `app_host: str = "127.0.0.1"`, `app_port: int = 8000`. Module-level `settings = Settings()` singleton with lazy lru_cache
  - Create `config/ruang.py` with `RUANG_LIST: list[str]` placeholder containing exactly: `["Poli Umum", "Poli Gigi", "KIA", "KB", "Imunisasi", "Lab", "Apotek", "IGD", "Pendaftaran"]` plus a comment block telling the user to edit this file with actual ruang names
  - Create `config/selectors.yaml` schema (placeholder values, Task 7 fills with discovered selectors): keys for `login.puskesmas_select`, `login.username_input`, `login.password_input`, `login.submit_button`, `dashboard.pendaftaran_induk_button`, `daftar.date_filter`, `daftar.ruang_filter`, `daftar.apply_filter_button`, `daftar.patient_table`, `daftar.patient_row`, `daftar.detail_modal_or_page`, `detail.tindakan_table`, `detail.biaya_field`, `pagination.next_button`, `pagination.page_indicator`, `session.login_redirect_url_pattern`
  - Create `config/selectors.py` with `Selectors` Pydantic model that validates `selectors.yaml` shape on load, plus `load_selectors() -> Selectors` function with lru_cache
  - Write tests `tests/test_config.py`:
    - RED: `test_settings_loads_from_env` (uses monkeypatch to set env, asserts values)
    - RED: `test_settings_missing_required_fails` (missing EMR_USERNAME → ValidationError)
    - RED: `test_ruang_list_non_empty` (assert list len ≥ 1, all strings)
    - RED: `test_selectors_yaml_loads` (loads default yaml, validates shape)
    - RED: `test_selectors_yaml_invalid_raises` (corrupt yaml → ValidationError)
  - Then implement until GREEN

  **Must NOT do**:
  - Do NOT log `emr_password` value anywhere (use `SecretStr`)
  - Do NOT use global mutable state for settings (lru_cache singleton only)
  - Do NOT hardcode selectors anywhere outside selectors.yaml
  - Do NOT add `Optional` to required env vars (fail fast on missing config)
  - Do NOT include `humanized_delay_ms` config (defer to Task 13 if needed)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard config pattern, well-defined Pydantic schemas
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3, 5, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: 9, 10, 11, 12, 13 (scraper modules need settings + selectors)
  - **Blocked By**: 1

  **References**:

  **External References**:
  - Pydantic Settings: `https://docs.pydantic.dev/latest/concepts/pydantic_settings/` - `BaseSettings` + env loading
  - Pydantic SecretStr: `https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr` - prevents accidental log leaks
  - PyYAML safe_load: `https://pyyaml.org/wiki/PyYAMLDocumentation` - `yaml.safe_load` (NOT `load`)

  **WHY Each Reference Matters**:
  - `BaseSettings` reads from `.env` natively, no manual `os.getenv` boilerplate
  - `SecretStr` redacts password in `repr()` and logs (defense in depth for medical app)
  - `safe_load` prevents YAML deserialization attacks (medical app = security-sensitive)

  **Acceptance Criteria**:
  - [ ] `Test-Path config/settings.py, config/ruang.py, config/selectors.yaml, config/selectors.py`
  - [ ] `pytest tests/test_config.py -v` exits 0 with 5+ passed
  - [ ] `python -c "from config.settings import settings; print(type(settings.emr_password).__name__)"` outputs `SecretStr`
  - [ ] `python -c "from config.ruang import RUANG_LIST; print(len(RUANG_LIST))"` outputs ≥ 9

  **QA Scenarios**:

  ```
  Scenario: Settings load from .env file with secret password redaction
    Tool: Bash
    Preconditions: .env contains valid EMR_USERNAME and EMR_PASSWORD
    Steps:
      1. Run: python -c "from config.settings import settings; print(repr(settings.emr_password))"
      2. Assert output contains "SecretStr('**********')" (NOT actual password)
      3. Run: python -c "from config.settings import settings; print(settings.emr_username.get_secret_value()[:1])"
      4. Assert exits 0 (can read but only via explicit method)
    Expected Result: Password never appears in repr; explicit access required
    Failure Indicators: Plaintext password in repr, AttributeError
    Evidence: .sisyphus/evidence/task-4-secret-redaction.txt

  Scenario: Missing required env var produces clear error
    Tool: Bash
    Preconditions: Temporarily empty .env
    Steps:
      1. Run: $env:EMR_USERNAME=""; python -c "from config.settings import Settings; Settings()"
      2. Assert exit code != 0
      3. Assert stderr contains "ValidationError" and "emr_username"
    Expected Result: Fails fast with clear message
    Failure Indicators: Silently uses None / empty default
    Evidence: .sisyphus/evidence/task-4-missing-env.txt

  Scenario: Selectors YAML loads and validates against schema
    Tool: Bash
    Preconditions: config/selectors.yaml exists
    Steps:
      1. Run: python -c "from config.selectors import load_selectors; s=load_selectors(); print(s.login.username_input)"
      2. Assert exits 0 with non-empty string output
    Expected Result: YAML loads, schema validates, accessor works
    Failure Indicators: KeyError, ValidationError, FileNotFoundError
    Evidence: .sisyphus/evidence/task-4-selectors.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-4-secret-redaction.txt`
  - [ ] `.sisyphus/evidence/task-4-missing-env.txt`
  - [ ] `.sisyphus/evidence/task-4-selectors.txt`
  - [ ] `.sisyphus/evidence/task-4-pytest.txt`

  **Commit**: YES
  - Message: `feat(config): env loader and selectors yaml schema`
  - Files: `config/settings.py`, `config/ruang.py`, `config/selectors.yaml`, `config/selectors.py`, `tests/test_config.py`
  - Pre-commit: `pytest tests/test_config.py -v`

- [x] 5. **SQLAlchemy models**

  **What to do**:
  - Create `models/base.py` with declarative `Base = declarative_base()` and `TimestampMixin` (`created_at`, `updated_at` with `func.now()`)
  - Create `models/visit.py` with `PatientVisit` model: `id` (PK), `no_rm` (str, indexed), `nama` (str), `tgl_lahir` (Date, nullable), `ruang` (str, indexed), `tanggal_kunjungan` (Date, indexed), `total_biaya` (Numeric(15,2)), `scrape_job_id` (FK), `created_at`, `updated_at`. Unique constraint on (`no_rm`, `tanggal_kunjungan`, `ruang`).
  - Create `models/treatment.py` with `Treatment` model: `id` (PK), `visit_id` (FK to PatientVisit), `nama_tindakan` (str), `biaya` (Numeric(15,2)), relationship `visit = relationship("PatientVisit", back_populates="treatments")`
  - In `PatientVisit`: `treatments = relationship("Treatment", back_populates="visit", cascade="all, delete-orphan")`
  - Create `models/job.py` with `ScrapeJob` model: `id` (PK), `status` (Enum: `pending`, `running`, `done`, `error`, `cancelled`), `started_at`, `finished_at`, `tanggal_from` (Date), `tanggal_to` (Date), `ruang_filter` (str, nullable for all-ruang), `error_message` (str, nullable), `total_visits_scraped` (int, default 0)
  - Create `models/recap.py` with `DailyRecap` model: `id` (PK), `tanggal_kunjungan` (Date, UNIQUE), `total_biaya` (Numeric(15,2)), `total_pasien` (int), `total_tindakan` (int), `last_scraped_at` (DateTime), `last_job_id` (FK to ScrapeJob)
  - Create `models/__init__.py` re-exporting all models
  - Tests `tests/test_models.py`:
    - RED: `test_visit_creation` (create + commit + query back)
    - RED: `test_visit_treatment_cascade` (delete visit → treatments deleted)
    - RED: `test_visit_unique_constraint` (duplicate no_rm+tanggal+ruang → IntegrityError)
    - RED: `test_recap_unique_per_date` (duplicate tanggal_kunjungan → IntegrityError)
    - RED: `test_job_status_enum` (invalid status raises)

  **Must NOT do**:
  - Do NOT add columns beyond the spec (no `created_by`, `notes`, `tags` etc.)
  - Do NOT use `Float` for currency (must use `Numeric(15,2)` for money accuracy)
  - Do NOT skip the unique constraint (re-scrape upsert correctness depends on it)
  - Do NOT use `String` without length where DB cares (use `String(255)` for `nama`, `String(50)` for `no_rm`)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Schema design has ripple effects on entire app; needs careful review of constraints
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3, 4, 6, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: 8, 15, 22
  - **Blocked By**: 1

  **References**:

  **External References**:
  - SQLAlchemy 2.0 ORM: `https://docs.sqlalchemy.org/en/20/orm/quickstart.html` - new declarative style
  - Numeric for currency: `https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Numeric`
  - Cascade delete: `https://docs.sqlalchemy.org/en/20/orm/cascades.html#delete-orphan`

  **WHY Each Reference Matters**:
  - SQLAlchemy 2.0 syntax is required (we're using 2.x async)
  - `Numeric(15,2)` prevents floating-point rounding bugs in money totals (1.1 + 2.2 ≠ 3.3 with Float)
  - `delete-orphan` ensures treatments don't outlive their visit (data integrity)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_models.py -v` exits 0 with 5+ passed
  - [ ] `python -c "from models import PatientVisit, Treatment, ScrapeJob, DailyRecap; print('ok')"` exits 0
  - [ ] All money columns use `Numeric(15,2)` (verified by grep)

  **QA Scenarios**:

  ```
  Scenario: Visit + treatments persist with cascade delete
    Tool: Bash
    Preconditions: Models defined; test DB available
    Steps:
      1. Run: pytest tests/test_models.py::test_visit_treatment_cascade -v
      2. Assert PASS
    Expected Result: Deleting visit cascades to treatments
    Failure Indicators: Orphan treatments remain after visit delete
    Evidence: .sisyphus/evidence/task-5-cascade.txt

  Scenario: Money columns use Numeric not Float
    Tool: Bash (grep)
    Preconditions: Models created
    Steps:
      1. Run: Get-ChildItem models/*.py | Select-String "Float|Real"
      2. Assert no matches
      3. Run: Get-ChildItem models/*.py | Select-String "Numeric\(15"
      4. Assert at least 2 matches (visit.total_biaya, treatment.biaya, recap.total_biaya)
    Expected Result: All currency uses Numeric(15,2)
    Failure Indicators: Float type found for any money field
    Evidence: .sisyphus/evidence/task-5-numeric.txt

  Scenario: Unique constraint prevents duplicate same-date-same-ruang visits
    Tool: Bash
    Preconditions: Test DB seeded
    Steps:
      1. Run: pytest tests/test_models.py::test_visit_unique_constraint -v
      2. Assert PASS (IntegrityError raised on duplicate)
    Expected Result: Re-scrape doesn't double-insert
    Failure Indicators: Duplicate inserted silently
    Evidence: .sisyphus/evidence/task-5-unique.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-5-cascade.txt`
  - [ ] `.sisyphus/evidence/task-5-numeric.txt`
  - [ ] `.sisyphus/evidence/task-5-unique.txt`
  - [ ] `.sisyphus/evidence/task-5-pytest.txt`

  **Commit**: YES
  - Message: `feat(models): sqlalchemy models for visit, treatment, job, recap`
  - Files: `models/base.py`, `models/visit.py`, `models/treatment.py`, `models/job.py`, `models/recap.py`, `models/__init__.py`, `tests/test_models.py`
  - Pre-commit: `pytest tests/test_models.py -v`

- [x] 6. **Pydantic schemas (request/response DTOs)**

  **What to do**:
  - Create `app/schemas/__init__.py` and `app/schemas/dto.py` with:
    - `DateMode` Literal `["single", "range"]`
    - `ScrapeRequest`: `mode: DateMode`, `tanggal_from: date`, `tanggal_to: date | None`, `ruang: str | None` (None = all). Validator: if mode==single, `tanggal_to` defaults to `tanggal_from`; if mode==range, both required and from ≤ to; range max 31 days
    - `ScrapeJobOut`: `id`, `status`, `started_at`, `finished_at`, `tanggal_from`, `tanggal_to`, `ruang_filter`, `total_visits_scraped`, `error_message`
    - `TreatmentOut`: `nama_tindakan`, `biaya: Decimal`
    - `VisitOut`: `id`, `no_rm`, `nama`, `tgl_lahir`, `ruang`, `tanggal_kunjungan`, `total_biaya: Decimal`, `treatments: list[TreatmentOut]`
    - `RecapOut`: `tanggal_kunjungan`, `total_biaya: Decimal`, `total_pasien`, `total_tindakan`, `last_scraped_at`
    - `ProgressEvent`: `event_type: Literal["log","progress","row","done","error","cancelled"]`, `message: str`, `current: int | None`, `total: int | None`, `payload: dict | None`
  - All `from_attributes=True` model_config for ORM compatibility
  - Tests `tests/test_schemas.py`:
    - RED: `test_scrape_request_single_mode_defaults_to_single_day`
    - RED: `test_scrape_request_range_validates_order`
    - RED: `test_scrape_request_range_max_31_days`
    - RED: `test_visit_out_serializes_decimal_to_string`
    - RED: `test_progress_event_validates_event_type`

  **Must NOT do**:
  - Do NOT use `float` for `biaya` (always `Decimal`)
  - Do NOT add fields not used by API (no `created_by`, `tags`, `notes`)
  - Do NOT mix request and response models in same class

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard Pydantic DTOs, no special domain reasoning
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3, 4, 5, 7)
  - **Parallel Group**: Wave 1
  - **Blocks**: 14, 17, 18, 19
  - **Blocked By**: 1

  **References**:

  **External References**:
  - Pydantic v2 validators: `https://docs.pydantic.dev/latest/concepts/validators/#field-validators`
  - Pydantic Decimal: `https://docs.pydantic.dev/latest/api/standard_library_types/#decimaldecimal`
  - Pydantic ORM mode: `https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances`

  **WHY Each Reference Matters**:
  - Validators enforce 31-day max prevents user from accidentally scraping a year of data (rate limit / session timeout protection)
  - `Decimal` over `float` consistent with DB Numeric columns
  - `from_attributes=True` lets us pass ORM objects directly to FastAPI response_model

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_schemas.py -v` exits 0 with 5+ passed
  - [ ] `python -c "from app.schemas.dto import ScrapeRequest; ScrapeRequest(mode='single', tanggal_from='2026-05-15')"` exits 0
  - [ ] No `float` used for money (verified by grep)

  **QA Scenarios**:

  ```
  Scenario: Range mode with from > to is rejected
    Tool: Bash
    Preconditions: Schemas implemented
    Steps:
      1. Run: python -c "from app.schemas.dto import ScrapeRequest; ScrapeRequest(mode='range', tanggal_from='2026-05-20', tanggal_to='2026-05-15')"
      2. Assert exits non-zero with ValidationError
    Expected Result: Backwards date range rejected
    Failure Indicators: Accepts invalid range
    Evidence: .sisyphus/evidence/task-6-range-validation.txt

  Scenario: Range exceeding 31 days is rejected
    Tool: Bash
    Preconditions: Schemas implemented
    Steps:
      1. Run: python -c "from app.schemas.dto import ScrapeRequest; ScrapeRequest(mode='range', tanggal_from='2026-01-01', tanggal_to='2026-03-15')"
      2. Assert exits non-zero with "31"
    Expected Result: 31-day cap enforced
    Failure Indicators: Accepts year-long range
    Evidence: .sisyphus/evidence/task-6-range-cap.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-6-range-validation.txt`
  - [ ] `.sisyphus/evidence/task-6-range-cap.txt`
  - [ ] `.sisyphus/evidence/task-6-pytest.txt`

  **Commit**: YES
  - Message: `feat(schemas): pydantic dtos for api contracts`
  - Files: `app/schemas/__init__.py`, `app/schemas/dto.py`, `tests/test_schemas.py`
  - Pre-commit: `pytest tests/test_schemas.py -v`

- [x] 7. **EMR site discovery + selector documentation**

  **What to do**:
  - Run a one-off discovery session: launch Playwright in **visible** mode, manually trace the EMR flow once, save HTML snapshots and screenshots at each step
  - Save snapshots to `tests/fixtures/emr/`:
    - `01-login.html` + `01-login.png` (initial page with Select2 + credentials form)
    - `02-after-login.html` + `02-after-login.png` (dashboard with PENDAFTARAN INDUK button)
    - `03-pendaftaran-induk.html` + `03-pendaftaran-induk.png` (page at `/px/1/1/0/0` with patient table + filters)
    - `04-detail-page-or-modal.html` + `04-detail-page-or-modal.png` (after clicking a patient row — captures whether it's modal/new page/inline)
  - **Anonymize HTML**: replace any real patient data (No RM, names, dates) with placeholder values (`PATIENT_001`, `Nama Sample`, `2026-01-01`) before committing
  - Update `config/selectors.yaml` with REAL CSS/XPath selectors discovered (replace placeholders from Task 4)
  - Document discovered behavior in `docs/EMR-FLOW.md` (this is allowed — it's a docs file, not source):
    - Row click behavior: modal | navigation | inline expansion (one of these, with concrete evidence)
    - Pagination: present | absent (and selectors if present)
    - Date filter mechanics: form submit | AJAX | URL param
    - Session timeout observed (if known)
    - Anti-bot signals (if any: rate limit headers, CAPTCHA triggers)
  - Add a `discovery/` script `discovery/capture_flow.py` that re-runs the capture flow (parameterized by env credentials) for future re-discovery if EMR changes

  **Must NOT do**:
  - Do NOT commit real patient data to fixtures (anonymize first; this is medical PII)
  - Do NOT skip anonymization for "speed"
  - Do NOT commit credentials in any file
  - Do NOT base scraper logic on assumed selectors (this task EXISTS to discover them)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Open-ended investigation with significant uncertainty; requires careful judgment about anonymization and selector stability
  - **Skills**: `[]` (Sisyphus has Playwright via env; Playwright skill is for browser-based QA verification, not scraper authoring)

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3, 4, 5, 6) - but produces selectors needed for Wave 2 scraper tasks
  - **Parallel Group**: Wave 1 (last to finish typically; Wave 2 scraper tasks consume its output)
  - **Blocks**: 10, 11, 12, 13 (all scraper modules need real selectors)
  - **Blocked By**: 1

  **References**:

  **External References**:
  - Playwright codegen: `https://playwright.dev/python/docs/codegen` - record interactions to learn selectors
  - Playwright trace viewer: `https://playwright.dev/python/docs/trace-viewer-intro` - debug captured flows
  - CSS selector resilience: `https://www.checklyhq.com/learn/playwright/best-practices/` - prefer role/text selectors over deep CSS chains

  **WHY Each Reference Matters**:
  - Codegen mode produces baseline selector candidates fast
  - Trace viewer is invaluable when EMR breaks the flow halfway
  - Resilient selectors (role+text) survive minor EMR redesigns better than `div > div:nth-child(3)` chains

  **Acceptance Criteria**:
  - [ ] All 4 HTML fixture pairs exist in `tests/fixtures/emr/`
  - [ ] `Get-ChildItem tests/fixtures/emr/*.html | Select-String "[A-Z][a-z]+ [A-Z][a-z]+"` returns NO matches looking like real names (anonymization check)
  - [ ] `config/selectors.yaml` no longer contains the placeholder string `TODO` or `<discover>`
  - [ ] `Test-Path docs/EMR-FLOW.md` returns True
  - [ ] `docs/EMR-FLOW.md` documents row-click behavior explicitly (one of: modal/navigation/inline)

  **QA Scenarios**:

  ```
  Scenario: Discovery script reruns and captures all 4 stages
    Tool: Bash
    Preconditions: Valid .env with credentials
    Steps:
      1. Run: python discovery/capture_flow.py
      2. Assert exit 0
      3. Run: Get-ChildItem tests/fixtures/emr/ | Measure-Object | Select-Object Count
      4. Assert at least 8 files (4 HTML + 4 PNG)
    Expected Result: Reproducible discovery flow
    Failure Indicators: Login fails, missing snapshots, script crashes
    Evidence: .sisyphus/evidence/task-7-discovery-output.txt + .sisyphus/evidence/task-7-fixtures-listing.txt

  Scenario: HTML fixtures contain no real PII
    Tool: Bash
    Preconditions: Fixtures committed
    Steps:
      1. Run: Get-ChildItem tests/fixtures/emr/*.html | ForEach-Object { Get-Content $_.FullName -Raw } | Select-String "(?i)\b(no rm|nik)\s*[:=]\s*\d{6,}"
      2. Assert no high-cardinality digit sequences match (anonymization confirmed)
      3. Run: Get-ChildItem tests/fixtures/emr/*.html | Select-String "PATIENT_00\d|Sample"
      4. Assert at least one match (placeholder names present)
    Expected Result: All real identifiers replaced
    Failure Indicators: Real-looking RM numbers or full names remain
    Evidence: .sisyphus/evidence/task-7-pii-check.txt

  Scenario: Selectors YAML now has discovered real selectors
    Tool: Bash
    Preconditions: After discovery
    Steps:
      1. Run: Get-Content config/selectors.yaml
      2. Assert no "TODO" or "<discover>" placeholder remains
      3. Run: python -c "from config.selectors import load_selectors; s=load_selectors(); print(len(s.login.username_input))"
      4. Assert non-empty selector strings
    Expected Result: Selectors documented from real EMR
    Failure Indicators: Placeholders remain, schema validation fails
    Evidence: .sisyphus/evidence/task-7-selectors-final.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-7-discovery-output.txt`
  - [ ] `.sisyphus/evidence/task-7-fixtures-listing.txt`
  - [ ] `.sisyphus/evidence/task-7-pii-check.txt`
  - [ ] `.sisyphus/evidence/task-7-selectors-final.txt`

  **Commit**: YES
  - Message: `docs(scraper): emr selector discovery and documentation`
  - Files: `tests/fixtures/emr/*.html`, `tests/fixtures/emr/*.png`, `config/selectors.yaml` (updated), `docs/EMR-FLOW.md`, `discovery/capture_flow.py`
  - Pre-commit: PII anonymization check + selectors schema validates

- [x] 8. **Database session + repository layer**

  **What to do**:
  - Create `app/db/__init__.py` and `app/db/session.py`: async engine using `settings.database_url`, async sessionmaker, `get_session()` dependency for FastAPI
  - Create `app/db/init_db.py`: `init_db()` function that creates all tables via `Base.metadata.create_all` (using sync engine for migration only; runtime is async). Idempotent — safe to call on every app start.
  - Create `app/db/repositories/__init__.py` plus 4 repository modules (one concern per file):
    - `app/db/repositories/visit_repo.py`: `add_visit_with_treatments(session, visit_data, treatments)`, `list_visits(session, tanggal_from, tanggal_to, ruang)`, `upsert_visit(session, visit_data, treatments)` (delete existing treatments + insert new on conflict)
    - `app/db/repositories/job_repo.py`: `create_job(session, request)`, `update_job_status(session, job_id, status, error=None)`, `get_active_job(session)` (returns running job if any), `increment_visit_count(session, job_id)`
    - `app/db/repositories/recap_repo.py`: `upsert_recap(session, tanggal_kunjungan, totals, job_id)` (compute total_biaya/total_pasien/total_tindakan from visits, INSERT OR UPDATE), `list_recaps(session, limit=50)`, `get_recap_by_date(session, tanggal)`
  - Tests `tests/test_repositories.py`:
    - RED: `test_add_visit_with_treatments_persists`
    - RED: `test_upsert_visit_replaces_treatments` (rescrape replaces, not appends)
    - RED: `test_recap_upsert_inserts_then_updates_on_same_date`
    - RED: `test_get_active_job_returns_running_only`
    - RED: `test_list_visits_filters_by_date_and_ruang`

  **Must NOT do**:
  - Do NOT use sync session at runtime (only in `init_db.py` for table creation)
  - Do NOT add raw SQL strings (use SQLAlchemy expressions)
  - Do NOT skip transaction context (`async with session.begin()`)
  - Do NOT add `delete_all_visits` or other dangerous bulk ops
  - Do NOT add a `cache` layer in repos (premature optimization)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Repository correctness is critical for upsert semantics; needs careful transaction handling
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9-14 once T5 done)
  - **Parallel Group**: Wave 2
  - **Blocks**: 15, 17, 19, 22
  - **Blocked By**: 5

  **References**:

  **Pattern References**:
  - `models/__init__.py` (Task 5 output) - import all models for relationship resolution

  **External References**:
  - SQLAlchemy 2.x async sessions: `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncio-scoped-session`
  - SQLite UPSERT: `https://www.sqlite.org/lang_upsert.html` - `INSERT ... ON CONFLICT DO UPDATE`
  - SQLAlchemy `insert().on_conflict_do_update`: `https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#insert-on-conflict-upsert`

  **WHY Each Reference Matters**:
  - Async session pattern is non-trivial; copying canonical example avoids subtle bugs
  - SQLite UPSERT is the right primitive for "re-scrape updates record" requirement
  - Dialect-specific upsert is more reliable than try/except SELECT-then-INSERT-or-UPDATE

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_repositories.py -v` exits 0 with 5+ passed
  - [ ] `python -c "from app.db.session import get_session; print('ok')"` exits 0
  - [ ] `Get-ChildItem app/db/repositories/*.py | Select-String "TEXT|raw_sql"` returns no matches (no raw SQL)

  **QA Scenarios**:

  ```
  Scenario: Re-scraping same visit replaces treatments not duplicates
    Tool: Bash
    Preconditions: Repos and models in place
    Steps:
      1. Run: pytest tests/test_repositories.py::test_upsert_visit_replaces_treatments -v
      2. Assert PASS
    Expected Result: Second upsert with different treatments → treatments table has only the second set
    Failure Indicators: Both treatment sets present (duplicate), or DB error
    Evidence: .sisyphus/evidence/task-8-upsert.txt

  Scenario: Recap upsert: insert then update on same date
    Tool: Bash
    Preconditions: Empty test DB
    Steps:
      1. Run: pytest tests/test_repositories.py::test_recap_upsert_inserts_then_updates_on_same_date -v
      2. Assert PASS
    Expected Result: One row in daily_recap, total_biaya updated, last_scraped_at advanced
    Failure Indicators: Two rows (duplicate), or stale total
    Evidence: .sisyphus/evidence/task-8-recap-upsert.txt

  Scenario: Active job lock prevents concurrent triggers
    Tool: Bash
    Preconditions: Empty DB
    Steps:
      1. Run: pytest tests/test_repositories.py::test_get_active_job_returns_running_only -v
      2. Assert PASS
    Expected Result: When a running job exists, get_active_job returns it; after status=done, returns None
    Failure Indicators: Returns None for running job, or returns done jobs
    Evidence: .sisyphus/evidence/task-8-active-job.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-8-upsert.txt`
  - [ ] `.sisyphus/evidence/task-8-recap-upsert.txt`
  - [ ] `.sisyphus/evidence/task-8-active-job.txt`
  - [ ] `.sisyphus/evidence/task-8-pytest.txt`

  **Commit**: YES
  - Message: `feat(db): async session and repository layer`
  - Files: `app/db/__init__.py`, `app/db/session.py`, `app/db/init_db.py`, `app/db/repositories/*.py`, `tests/test_repositories.py`
  - Pre-commit: `pytest tests/test_repositories.py -v`

- [x] 9. **Playwright browser context manager**

  **What to do**:
  - Create `scraper/__init__.py` and `scraper/browser.py` with:
    - Async context manager `playwright_browser(headless: bool | None = None)` that yields `(browser, context, page)`
    - Reads `BROWSER_MODE` from settings if `headless` arg is None
    - Sets viewport `{width: 1366, height: 768}` (typical desktop)
    - Sets user agent to a recent Chrome string
    - Sets default timeout via `settings.scrape_timeout * 1000`
    - On exit: closes context, closes browser, stops playwright (proper cleanup order)
  - Create `scraper/screenshot.py`: `save_screenshot(page, label)` writes `.sisyphus/evidence/scraper/{timestamp}-{label}.png`. Used for debugging and on errors
  - Tests `tests/test_browser.py`:
    - RED: `test_browser_launches_and_closes` (use real chromium, navigate to about:blank, assert URL)
    - RED: `test_browser_respects_browser_mode_env` (mock setting, assert headless flag)
    - RED: `test_screenshot_saves_to_evidence_dir`

  **Must NOT do**:
  - Do NOT use sync Playwright API (`playwright.sync_api`)
  - Do NOT leave browsers running on exception (must `try/finally` cleanup)
  - Do NOT use real EMR site for tests (use about:blank or local fixture)
  - Do NOT pin a specific Chrome version inline (use Playwright's bundled)
  - Do NOT add `time.sleep()` anywhere

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Async resource lifecycle has subtle bugs (zombie browsers); needs correct teardown discipline
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 14)
  - **Parallel Group**: Wave 2
  - **Blocks**: 10, 11, 12, 13
  - **Blocked By**: 4

  **References**:

  **External References**:
  - Playwright async API: `https://playwright.dev/python/docs/api/class-playwright`
  - Browser context isolation: `https://playwright.dev/python/docs/browser-contexts`

  **WHY Each Reference Matters**:
  - Async context manager is canonical pattern; minor errors leak processes
  - Per-job browser context isolates state (cookies, storage) between scrape runs

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_browser.py -v` exits 0 with 3+ passed
  - [ ] `Get-ChildItem scraper/*.py | Select-String "playwright\.sync_api"` returns no matches
  - [ ] `Get-ChildItem scraper/*.py | Select-String "time\.sleep"` returns no matches

  **QA Scenarios**:

  ```
  Scenario: Browser launches in headless mode and closes cleanly
    Tool: Bash
    Preconditions: Playwright + chromium installed
    Steps:
      1. Run: pytest tests/test_browser.py::test_browser_launches_and_closes -v
      2. Assert PASS
      3. Run: Get-Process chrome*, msedge* -ErrorAction SilentlyContinue
      4. Assert no zombie chromium processes
    Expected Result: Browser opens, navigates, closes; no leaks
    Failure Indicators: Test fails, or zombie processes remain
    Evidence: .sisyphus/evidence/task-9-launch.txt

  Scenario: Visible mode toggle works
    Tool: Bash
    Preconditions: BROWSER_MODE settable
    Steps:
      1. Run: pytest tests/test_browser.py::test_browser_respects_browser_mode_env -v
      2. Assert PASS
    Expected Result: BROWSER_MODE=visible launches headed; default headless
    Failure Indicators: Always headless or always visible
    Evidence: .sisyphus/evidence/task-9-mode.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-9-launch.txt`
  - [ ] `.sisyphus/evidence/task-9-mode.txt`
  - [ ] `.sisyphus/evidence/task-9-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): playwright browser context manager`
  - Files: `scraper/__init__.py`, `scraper/browser.py`, `scraper/screenshot.py`, `tests/test_browser.py`
  - Pre-commit: `pytest tests/test_browser.py -v`

- [x] 10. **Scraper - login flow module**

  **What to do**:
  - Create `scraper/login.py` with:
    - `async def login(page, selectors, settings) -> None`
    - Step 1: Navigate to `settings.emr_base_url`, wait for `selectors.login.puskesmas_select` visible
    - Step 2: Open Select2 dropdown (click trigger → wait for options → click matching `settings.emr_puskesmas`). Use `page.select_option` if it's native `<select>` first; fallback to JS-driven Select2 click pattern
    - Step 3: Fill `selectors.login.username_input` with `settings.emr_username.get_secret_value()`
    - Step 4: Fill `selectors.login.password_input` with `settings.emr_password.get_secret_value()`
    - Step 5: Click `selectors.login.submit_button`
    - Step 6: Wait for navigation OR DOM change indicating success: `selectors.dashboard.pendaftaran_induk_button` visible (success) OR error banner visible (raise `LoginError`)
    - Custom exceptions in `scraper/exceptions.py`: `LoginError`, `SelectorNotFoundError`, `SessionExpiredError`, `RateLimitError`
    - Logging: log "Login attempt for puskesmas {puskesmas}" — NEVER log username or password
  - Tests `tests/test_login.py`:
    - RED: `test_login_success_with_fixture` (load `tests/fixtures/emr/01-login.html` via local file URL, mock submit, assert no exception)
    - RED: `test_login_invalid_creds_raises_login_error` (fixture with error banner)
    - RED: `test_login_redacts_credentials_in_logs` (capture logs, assert username/password absent)
    - RED: `test_login_select2_option_selected` (Select2 interaction works)

  **Must NOT do**:
  - Do NOT log credentials in any form (assert in test)
  - Do NOT hardcode selector strings (use `selectors` arg)
  - Do NOT swallow login failures (raise specific exception)
  - Do NOT use `page.fill` without `wait_for_selector` first

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Select2 interaction is finicky; needs investigation of whether real EMR uses native select vs JS-driven; failure modes need careful exception design
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 11, 12, 13 conceptually but depends on T7 selectors and T9 browser)
  - **Parallel Group**: Wave 2
  - **Blocks**: 11, 15
  - **Blocked By**: 4, 7, 9

  **References**:

  **Pattern References**:
  - `scraper/browser.py` (Task 9) - context manager usage
  - `config/selectors.yaml` (Task 7) - real selector keys

  **External References**:
  - Playwright Select2: `https://playwright.dev/python/docs/api/class-locator#locator-select-option` - native select handling
  - Playwright wait strategies: `https://playwright.dev/python/docs/actionability` - prefer `wait_for_selector` over sleep

  **WHY Each Reference Matters**:
  - Select2 may wrap a native `<select>` (then `select_option` works) OR be pure-JS (then click trigger + click option). Discovery in T7 reveals which.
  - Wait strategies prevent flaky tests that pass locally but fail under load

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_login.py -v` exits 0 with 4+ passed
  - [ ] `Get-ChildItem scraper/login.py | Select-String "username|password|EMR_PASSWORD"` returns no log statements with values
  - [ ] `scraper/exceptions.py` defines all 4 exception classes

  **QA Scenarios**:

  ```
  Scenario: Login flow handles fixture login page successfully
    Tool: Bash
    Preconditions: Fixtures from T7, browser from T9
    Steps:
      1. Run: pytest tests/test_login.py::test_login_success_with_fixture -v
      2. Assert PASS
    Expected Result: Login function completes without exception against fixture
    Failure Indicators: SelectorNotFoundError, timeout
    Evidence: .sisyphus/evidence/task-10-login-success.txt

  Scenario: Credentials never appear in logs
    Tool: Bash
    Preconditions: Login function logs to capturable handler
    Steps:
      1. Run: pytest tests/test_login.py::test_login_redacts_credentials_in_logs -v
      2. Assert PASS
    Expected Result: Log records contain no plaintext password or username
    Failure Indicators: Test fails because credentials leaked
    Evidence: .sisyphus/evidence/task-10-redaction.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-10-login-success.txt`
  - [ ] `.sisyphus/evidence/task-10-redaction.txt`
  - [ ] `.sisyphus/evidence/task-10-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): login flow with select2 and credentials`
  - Files: `scraper/login.py`, `scraper/exceptions.py`, `tests/test_login.py`
  - Pre-commit: `pytest tests/test_login.py -v`

- [x] 11. **Scraper - navigation module**

  **What to do**:
  - Create `scraper/navigation.py` with:
    - `async def go_to_pendaftaran_induk(page, selectors) -> None`
    - Step 1: Verify `selectors.dashboard.pendaftaran_induk_button` visible (raise `SelectorNotFoundError` otherwise)
    - Step 2: Click button
    - Step 3: Wait for URL match `**/daf/px/1/1/0/0` OR for `selectors.daftar.patient_table` visible (whichever comes first)
    - Step 4: Sanity check: assert URL contains `/daf/px/` (raise `NavigationError`)
    - Add `NavigationError` to `scraper/exceptions.py`
    - `async def is_logged_in(page, selectors) -> bool` helper: returns True if dashboard button visible, False if redirected to login
  - Tests `tests/test_navigation.py`:
    - RED: `test_navigation_to_daftar_succeeds_with_fixture`
    - RED: `test_navigation_missing_button_raises`
    - RED: `test_is_logged_in_detects_redirect_to_login`

  **Must NOT do**:
  - Do NOT use `page.goto(url)` to bypass the click (we need real flow for state)
  - Do NOT use absolute URL match if EMR uses redirects/sessions (use partial URL match)
  - Do NOT add retry logic here (orchestrator handles retries)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: URL matching + DOM state interaction; subtle race conditions
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8-14 in Wave 2)
  - **Parallel Group**: Wave 2
  - **Blocks**: 12, 15
  - **Blocked By**: 4, 7, 9, 10

  **References**:

  **External References**:
  - Playwright `wait_for_url`: `https://playwright.dev/python/docs/api/class-page#page-wait-for-url` - URL matching with glob

  **WHY Each Reference Matters**:
  - Glob patterns (`**/daf/px/**`) survive query string variations

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_navigation.py -v` exits 0 with 3+ passed
  - [ ] No `time.sleep` calls
  - [ ] `Get-ChildItem scraper/navigation.py | Select-String "page\.goto"` returns no matches (use clicks for navigation)

  **QA Scenarios**:

  ```
  Scenario: Click PENDAFTARAN INDUK navigates to /px/1/1/0/0
    Tool: Bash
    Preconditions: Fixture for dashboard
    Steps:
      1. Run: pytest tests/test_navigation.py::test_navigation_to_daftar_succeeds_with_fixture -v
      2. Assert PASS
    Expected Result: URL ends with /daf/px/1/1/0/0; patient_table selector visible
    Failure Indicators: Stuck on dashboard, wrong URL, timeout
    Evidence: .sisyphus/evidence/task-11-navigation.txt

  Scenario: Session expiry detection works
    Tool: Bash
    Preconditions: Fixture simulating logout
    Steps:
      1. Run: pytest tests/test_navigation.py::test_is_logged_in_detects_redirect_to_login -v
      2. Assert PASS
    Expected Result: is_logged_in returns False when on login page
    Failure Indicators: Returns True incorrectly
    Evidence: .sisyphus/evidence/task-11-session.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-11-navigation.txt`
  - [ ] `.sisyphus/evidence/task-11-session.txt`
  - [ ] `.sisyphus/evidence/task-11-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): navigation to pendaftaran induk page`
  - Files: `scraper/navigation.py`, `scraper/exceptions.py` (updated), `tests/test_navigation.py`
  - Pre-commit: `pytest tests/test_navigation.py -v`

- [x] 12. **Scraper - filter module**

  **What to do**:
  - Create `scraper/filter.py` with:
    - `async def apply_filter(page, selectors, tanggal_from, tanggal_to, ruang) -> None`
    - Strategy depends on `docs/EMR-FLOW.md` from T7. Most likely: fill date input(s), select ruang, click apply
    - Wait for `selectors.daftar.patient_table` to refresh (use `page.wait_for_response` matching API URL if AJAX, or `wait_for_load_state` if form submit)
    - If `ruang is None`, leave ruang filter at default ("All") — verify the filter still applies
    - Add `FilterError` to `scraper/exceptions.py`
  - Date format helper: detect EMR's expected date format from T7 (DD/MM/YYYY, YYYY-MM-DD, etc.) and normalize Python `date` to EMR string
  - Tests `tests/test_filter.py`:
    - RED: `test_apply_filter_single_date_with_ruang`
    - RED: `test_apply_filter_with_no_ruang_means_all`
    - RED: `test_apply_filter_date_format_correct` (assert formatted string matches EMR format)
    - RED: `test_apply_filter_table_refresh_awaited`

  **Must NOT do**:
  - Do NOT loop over dates here (single application; orchestrator handles range loop)
  - Do NOT assume date format (must be configurable or discovered from T7)
  - Do NOT add `time.sleep`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Date format edge cases + AJAX vs form refresh detection
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 13, 15
  - **Blocked By**: 4, 7, 9, 11

  **References**:

  **External References**:
  - Playwright wait_for_response: `https://playwright.dev/python/docs/api/class-page#page-wait-for-response`
  - Python date formatting: `https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior`

  **WHY Each Reference Matters**:
  - `wait_for_response` is the right primitive for AJAX-driven tables (vs sleep + hope)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_filter.py -v` exits 0 with 4+ passed
  - [ ] No `time.sleep`

  **QA Scenarios**:

  ```
  Scenario: Filter with date and ruang updates table
    Tool: Bash
    Preconditions: Fixture for daftar page with filter form
    Steps:
      1. Run: pytest tests/test_filter.py::test_apply_filter_single_date_with_ruang -v
      2. Assert PASS
    Expected Result: After apply, table reflects filter
    Failure Indicators: Stale table, format error
    Evidence: .sisyphus/evidence/task-12-filter.txt

  Scenario: All-ruang mode (ruang=None) leaves default
    Tool: Bash
    Preconditions: Fixture
    Steps:
      1. Run: pytest tests/test_filter.py::test_apply_filter_with_no_ruang_means_all -v
      2. Assert PASS
    Expected Result: Ruang dropdown unchanged or set to "ALL"
    Failure Indicators: Tries to select non-existent option
    Evidence: .sisyphus/evidence/task-12-all-ruang.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-12-filter.txt`
  - [ ] `.sisyphus/evidence/task-12-all-ruang.txt`
  - [ ] `.sisyphus/evidence/task-12-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): emr filter for date and ruang`
  - Files: `scraper/filter.py`, `scraper/exceptions.py` (updated), `tests/test_filter.py`
  - Pre-commit: `pytest tests/test_filter.py -v`

- [x] 13. **Scraper - row extraction module (click-per-row)**

  **What to do**:
  - Create `scraper/extract.py` with:
    - `async def extract_visits(page, selectors, on_progress) -> list[VisitData]` where `VisitData` is a dataclass with `no_rm, nama, tgl_lahir, ruang, tanggal_kunjungan, total_biaya, treatments: list[TreatmentData]`
    - Step 1: Read patient table rows. Detect pagination presence. If paginated, loop pages.
    - Step 2: For each row: extract identity fields from row text content
    - Step 3: Click row → wait for detail (modal OR new page based on `docs/EMR-FLOW.md`) → extract `tindakan` rows + `biaya` per row → close modal/go-back
    - Step 4: Apply humanized delay 300-800ms (random) between row clicks (anti-bot guardrail per Metis)
    - Step 5: Call `on_progress(current, total, current_visit_summary)` callback after each row
    - Step 6: Pre-row session check: call `is_logged_in(page, selectors)` from T11. If False, raise `SessionExpiredError` (orchestrator handles re-login retry)
    - On any per-row failure: log warning, save screenshot, skip row, continue
  - Create `scraper/types.py` with `VisitData`, `TreatmentData` dataclasses (frozen, slots)
  - Tests `tests/test_extract.py`:
    - RED: `test_extract_visits_with_3_patients_fixture` (assert returns 3 items with correct treatment counts)
    - RED: `test_extract_handles_empty_table`
    - RED: `test_extract_handles_pagination` (fixture with 2 pages)
    - RED: `test_extract_calls_progress_callback_per_row`
    - RED: `test_extract_handles_session_expiry_mid_loop` (raises SessionExpiredError)
    - RED: `test_extract_skips_failed_row_continues_others`

  **Must NOT do**:
  - Do NOT parallelize row clicks (sequential per Metis anti-bot guidance)
  - Do NOT swallow ALL exceptions (let SessionExpiredError propagate; only catch per-row data errors)
  - Do NOT log full row content (PII redaction: log only `no_rm` first 2 chars + `[REDACTED]`)
  - Do NOT use `time.sleep` (use `page.wait_for_timeout(ms)` for the humanized delay since it's for a real anti-bot pause, not a flaky wait)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Most complex scraper logic; pagination + click-loop + session detection + error tolerance + PII redaction
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: 15
  - **Blocked By**: 4, 7, 9, 12

  **References**:

  **Pattern References**:
  - `scraper/navigation.py:is_logged_in` (T11) - session check helper
  - `tests/fixtures/emr/03-pendaftaran-induk.html` (T7) - row table structure
  - `tests/fixtures/emr/04-detail-page-or-modal.html` (T7) - detail structure

  **External References**:
  - Playwright `locator.all`: `https://playwright.dev/python/docs/api/class-locator#locator-all` - iterate row locators
  - Playwright `expect`: `https://playwright.dev/python/docs/api/class-locatorassertions` - resilient assertions

  **WHY Each Reference Matters**:
  - `locator.all()` returns frozen list, safe to iterate while DOM may re-render after clicks
  - `expect` retries with timeout, more resilient than imperative wait+assert

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_extract.py -v` exits 0 with 6+ passed
  - [ ] `Get-ChildItem scraper/extract.py | Select-String "logger\.info.*nama|logger\.info.*no_rm[^_]"` returns no matches with raw values
  - [ ] Humanized delay implemented (verified via test that measures elapsed time roughly matches expected delay)

  **QA Scenarios**:

  ```
  Scenario: Extract from 3-patient fixture returns correct structure
    Tool: Bash
    Preconditions: Fixtures from T7, browser from T9
    Steps:
      1. Run: pytest tests/test_extract.py::test_extract_visits_with_3_patients_fixture -v
      2. Assert PASS
    Expected Result: Returns list of 3 VisitData with treatments populated
    Failure Indicators: Wrong count, missing fields, wrong total_biaya
    Evidence: .sisyphus/evidence/task-13-extract.txt

  Scenario: Session expiry mid-loop is detected and propagated
    Tool: Bash
    Preconditions: Fixture forces logout halfway
    Steps:
      1. Run: pytest tests/test_extract.py::test_extract_handles_session_expiry_mid_loop -v
      2. Assert PASS (SessionExpiredError raised)
    Expected Result: Loop stops, exception propagated
    Failure Indicators: Silent failure, infinite loop
    Evidence: .sisyphus/evidence/task-13-session-expiry.txt

  Scenario: PII not present in logs
    Tool: Bash
    Preconditions: Capture log output
    Steps:
      1. Run: pytest tests/test_extract.py -v --log-cli-level=DEBUG 2>&1 | Out-File .sisyphus/evidence/task-13-logs.txt
      2. Run: Select-String -Path .sisyphus/evidence/task-13-logs.txt -Pattern "Nama Sample [A-Z]"
      3. Assert no full names in logs
    Expected Result: Names and full no_rm absent from logs
    Failure Indicators: PII appears in log output
    Evidence: .sisyphus/evidence/task-13-logs.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-13-extract.txt`
  - [ ] `.sisyphus/evidence/task-13-session-expiry.txt`
  - [ ] `.sisyphus/evidence/task-13-logs.txt`
  - [ ] `.sisyphus/evidence/task-13-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): row extraction with click-per-row strategy`
  - Files: `scraper/extract.py`, `scraper/types.py`, `tests/test_extract.py`
  - Pre-commit: `pytest tests/test_extract.py -v`

- [x] 14. **SSE progress event bus (in-memory pubsub)**

  **What to do**:
  - Create `app/progress/__init__.py` and `app/progress/event_bus.py`:
    - `EventBus` class wrapping `asyncio.Queue[ProgressEvent]` per `job_id`
    - Methods: `publish(job_id, event)`, `subscribe(job_id) -> AsyncIterator[ProgressEvent]`, `close(job_id)` (sentinel + cleanup)
    - Module-level singleton `event_bus = EventBus()`
    - Auto-cleanup queues for jobs that exited >1 hour ago (simple time-based)
  - Tests `tests/test_event_bus.py`:
    - RED: `test_publish_then_subscribe_yields_event`
    - RED: `test_close_terminates_subscription`
    - RED: `test_multiple_subscribers_per_job` (only single subscriber needed for v1, so this is a NEGATIVE test asserting only one supported is also valid)
    - RED: `test_unknown_job_subscribe_creates_queue`

  **Must NOT do**:
  - Do NOT add Redis/external pubsub (in-memory is fine for single-process)
  - Do NOT use `threading.Queue` (must be `asyncio.Queue`)
  - Do NOT persist events to DB (job log lives in `ScrapeJob.error_message` for failures only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Async pubsub correctness; subtle bugs around queue cleanup + cancellation
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9, 15 conceptually)
  - **Parallel Group**: Wave 2
  - **Blocks**: 15, 18, 21
  - **Blocked By**: 6

  **References**:

  **External References**:
  - Asyncio Queue: `https://docs.python.org/3/library/asyncio-queue.html`
  - sse-starlette: `https://github.com/sysid/sse-starlette` - integrates with FastAPI

  **WHY Each Reference Matters**:
  - asyncio.Queue is the canonical primitive
  - sse-starlette consumed by Task 18 to ship events to client

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_event_bus.py -v` exits 0 with 4+ passed
  - [ ] No threading imports in `app/progress/`

  **QA Scenarios**:

  ```
  Scenario: Publish/subscribe round trip
    Tool: Bash
    Preconditions: Event bus implemented
    Steps:
      1. Run: pytest tests/test_event_bus.py::test_publish_then_subscribe_yields_event -v
      2. Assert PASS
    Expected Result: Event reaches subscriber
    Failure Indicators: Hangs, missing event
    Evidence: .sisyphus/evidence/task-14-pubsub.txt

  Scenario: Close terminates subscription cleanly
    Tool: Bash
    Preconditions: After publish/subscribe
    Steps:
      1. Run: pytest tests/test_event_bus.py::test_close_terminates_subscription -v
      2. Assert PASS
    Expected Result: Subscriber's async iterator returns (StopAsyncIteration)
    Failure Indicators: Hangs forever
    Evidence: .sisyphus/evidence/task-14-close.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-14-pubsub.txt`
  - [ ] `.sisyphus/evidence/task-14-close.txt`
  - [ ] `.sisyphus/evidence/task-14-pytest.txt`

  **Commit**: YES
  - Message: `feat(progress): in-memory sse event bus`
  - Files: `app/progress/__init__.py`, `app/progress/event_bus.py`, `tests/test_event_bus.py`
  - Pre-commit: `pytest tests/test_event_bus.py -v`

- [x] 15. **Job orchestrator (state machine)**

  **What to do**:
  - Create `scraper/orchestrator.py` with:
    - `async def run_scrape_job(job_id: int, request: ScrapeRequest) -> None`
    - Acquires single-active-job lock (call `job_repo.get_active_job` — if exists, raise `JobAlreadyRunningError`)
    - Updates job status: `pending → running`
    - Iterate dates from `tanggal_from` to `tanggal_to` (inclusive). For each date:
      - Publish progress event "Login..."
      - `async with playwright_browser() as (browser, ctx, page):`
      - `await login(page, selectors, settings)`
      - `await go_to_pendaftaran_induk(page, selectors)`
      - `await apply_filter(page, selectors, date, date, request.ruang)`
      - `visits = await extract_visits(page, selectors, on_progress=publish_progress_callback)`
      - For each visit: `await visit_repo.upsert_visit(...)`
      - After date done: `await recap_repo.upsert_recap(date, ...)`
    - On `SessionExpiredError`: re-login + retry current date (max 1 retry)
    - On other errors: update job status `error`, persist `error_message`, publish `error` event
    - On cancellation: catch `asyncio.CancelledError`, update job status `cancelled`, persist partial results
    - On success: status `done`, publish `done` event with summary
    - `async def cancel_job(job_id) -> None`: sets cancellation flag (uses `asyncio.Task.cancel()`)
  - Tests `tests/test_orchestrator.py` (use mocks for browser/scraper modules):
    - RED: `test_orchestrator_happy_path` (mocked extract returns 2 visits → DB has 2 visits + 1 recap)
    - RED: `test_orchestrator_session_expiry_retries_once`
    - RED: `test_orchestrator_cancellation_persists_partial`
    - RED: `test_orchestrator_concurrent_trigger_rejected`
    - RED: `test_orchestrator_publishes_progress_events`

  **Must NOT do**:
  - Do NOT retry indefinitely on session expiry (max 1 retry per date)
  - Do NOT silently drop errors (always publish error event + persist message)
  - Do NOT skip the active-job lock (concurrent triggers → race conditions)
  - Do NOT add scheduling/cron logic (manual trigger only)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: State machine + error recovery + cancellation are the highest-stakes logic in the app
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on most of Wave 2)
  - **Parallel Group**: Wave 2 (last task in Wave 2)
  - **Blocks**: 18, 22
  - **Blocked By**: 5, 8, 10, 11, 12, 13, 14

  **References**:

  **Pattern References**:
  - All Wave 2 modules above

  **External References**:
  - asyncio cancellation: `https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel`

  **WHY Each Reference Matters**:
  - Cancellation in async Python has subtle semantics; documenting + testing is critical

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_orchestrator.py -v` exits 0 with 5+ passed
  - [ ] State transitions verified by test (status column reaches expected end state)

  **QA Scenarios**:

  ```
  Scenario: Happy path produces visits + recap
    Tool: Bash
    Preconditions: All Wave 2 modules in place
    Steps:
      1. Run: pytest tests/test_orchestrator.py::test_orchestrator_happy_path -v
      2. Assert PASS
    Expected Result: DB has expected visits and one recap row
    Failure Indicators: Wrong count, missing recap, wrong status
    Evidence: .sisyphus/evidence/task-15-happy.txt

  Scenario: Concurrent trigger is rejected
    Tool: Bash
    Preconditions: One job already running
    Steps:
      1. Run: pytest tests/test_orchestrator.py::test_orchestrator_concurrent_trigger_rejected -v
      2. Assert PASS (JobAlreadyRunningError)
    Expected Result: Second trigger raises immediately
    Failure Indicators: Both jobs run, DB corruption
    Evidence: .sisyphus/evidence/task-15-concurrent.txt

  Scenario: Cancellation persists partial results
    Tool: Bash
    Preconditions: Mid-job cancel
    Steps:
      1. Run: pytest tests/test_orchestrator.py::test_orchestrator_cancellation_persists_partial -v
      2. Assert PASS
    Expected Result: Status=cancelled; partial visits persisted; no exception escapes
    Failure Indicators: Exception escapes, DB rollback removes everything, status stuck on running
    Evidence: .sisyphus/evidence/task-15-cancel.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-15-happy.txt`
  - [ ] `.sisyphus/evidence/task-15-concurrent.txt`
  - [ ] `.sisyphus/evidence/task-15-cancel.txt`
  - [ ] `.sisyphus/evidence/task-15-pytest.txt`

  **Commit**: YES
  - Message: `feat(scraper): job orchestrator state machine`
  - Files: `scraper/orchestrator.py`, `tests/test_orchestrator.py`
  - Pre-commit: `pytest tests/test_orchestrator.py -v`

- [x] 16. **FastAPI app skeleton + middleware + lifespan**

  **What to do**:
  - Create `app/main.py` with `create_app()` factory: instantiates FastAPI, sets `lifespan` async context manager that runs `init_db()` on startup, mounts `static/` at `/static`, configures Jinja2 templates at `templates/`
  - Add request logging middleware (logs method + path + status + duration; redacts query strings if they could contain dates and PII — minimal here, dates are not PII)
  - CORS: NOT enabled (single-origin local app — explicit comment)
  - Add exception handlers for `LoginError`, `SessionExpiredError`, `JobAlreadyRunningError`, `ValidationError` → return appropriate JSON responses
  - Create `app/__main__.py` with `python -m app` entrypoint that runs uvicorn with `settings.app_host` and `settings.app_port`
  - Tests `tests/test_app.py`:
    - RED: `test_app_starts_and_serves_static` (TestClient, GET /static/css/output.css → 200)
    - RED: `test_app_lifespan_initializes_db` (after startup, DB tables exist)
    - RED: `test_login_error_handler_returns_401`
    - RED: `test_unknown_route_returns_404`

  **Must NOT do**:
  - Do NOT enable CORS for `*` (security — local app)
  - Do NOT add Prometheus metrics / OpenTelemetry (out of scope)
  - Do NOT mount admin / debug routes
  - Do NOT use blocking middleware (must be async)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard FastAPI app skeleton; pattern is well-known
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (gates Wave 3 routes)
  - **Parallel Group**: Wave 3 (first to start)
  - **Blocks**: 17, 18, 19
  - **Blocked By**: 8

  **References**:

  **External References**:
  - FastAPI lifespan: `https://fastapi.tiangolo.com/advanced/events/#lifespan` - replaces deprecated `@app.on_event`
  - FastAPI testing: `https://fastapi.tiangolo.com/tutorial/testing/`

  **WHY Each Reference Matters**:
  - `lifespan` is the modern replacement; old startup events are deprecated
  - TestClient enables fast smoke tests without spinning a real server

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_app.py -v` exits 0 with 4+ passed
  - [ ] `python -c "from app.main import create_app; app=create_app(); print(len(app.routes))"` exits 0

  **QA Scenarios**:

  ```
  Scenario: App boots, static assets serve, DB initialized
    Tool: Bash
    Preconditions: Wave 1 + 2 done
    Steps:
      1. Run: pytest tests/test_app.py::test_app_starts_and_serves_static -v
      2. Assert PASS
    Expected Result: 200 on /static/css/output.css; DB file exists with tables
    Failure Indicators: 404 static, missing DB tables
    Evidence: .sisyphus/evidence/task-16-boot.txt

  Scenario: Custom exception → mapped JSON response
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_app.py::test_login_error_handler_returns_401 -v
      2. Assert PASS
    Expected Result: LoginError → 401 with body {"error":"login_failed", ...}
    Failure Indicators: 500 generic error
    Evidence: .sisyphus/evidence/task-16-exception.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-16-boot.txt`
  - [ ] `.sisyphus/evidence/task-16-exception.txt`
  - [ ] `.sisyphus/evidence/task-16-pytest.txt`

  **Commit**: YES
  - Message: `feat(api): fastapi app skeleton with lifespan`
  - Files: `app/main.py`, `app/__main__.py`, `tests/test_app.py`
  - Pre-commit: `pytest tests/test_app.py -v`

- [x] 17. **Routes - GET / (index page) + GET /api/ruang**

  **What to do**:
  - Create `app/routes/__init__.py` and `app/routes/page.py`:
    - `@router.get("/", response_class=HTMLResponse)` renders `templates/index.html` with context `{ruang_list, today: date.today().isoformat()}`
  - Create `app/routes/api.py` with `@router.get("/api/ruang")` returning `{"ruang": RUANG_LIST}` from `config/ruang.py`
  - Register both routers in `app/main.py`
  - Tests `tests/test_routes_page.py`:
    - RED: `test_index_returns_200_with_today_date`
    - RED: `test_index_includes_ruang_list_in_html`
    - RED: `test_api_ruang_returns_list`

  **Must NOT do**:
  - Do NOT add server-side data fetching for visits/history here (Task 19 owns that)
  - Do NOT inline ruang options in HTML — they come from `/api/ruang` endpoint to keep templates lean
  - Do NOT add login form (no auth in v1)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Combines Jinja rendering + JSON API; small but mixed concerns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with 18, 19 once T16 done)
  - **Parallel Group**: Wave 3
  - **Blocks**: 20
  - **Blocked By**: 6, 8, 16

  **References**:

  **External References**:
  - FastAPI Jinja: `https://fastapi.tiangolo.com/advanced/templates/`

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_routes_page.py -v` exits 0 with 3+ passed
  - [ ] `curl http://127.0.0.1:8000/api/ruang` returns JSON with non-empty list (verified in app boot test)

  **QA Scenarios**:

  ```
  Scenario: Index page renders with form scaffolding
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_page.py::test_index_returns_200_with_today_date -v
      2. Assert PASS
    Expected Result: HTML response, status 200, contains today's date
    Failure Indicators: 500, missing date placeholder
    Evidence: .sisyphus/evidence/task-17-index.txt

  Scenario: Ruang API returns expected list
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_page.py::test_api_ruang_returns_list -v
      2. Assert PASS
    Expected Result: 200 with body {"ruang": [...9 entries]}
    Failure Indicators: Empty list, 500
    Evidence: .sisyphus/evidence/task-17-ruang.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-17-index.txt`
  - [ ] `.sisyphus/evidence/task-17-ruang.txt`
  - [ ] `.sisyphus/evidence/task-17-pytest.txt`

  **Commit**: YES
  - Message: `feat(api): index page and ruang list endpoint`
  - Files: `app/routes/__init__.py`, `app/routes/page.py`, `app/routes/api.py`, `app/main.py` (updated to register routers), `tests/test_routes_page.py`
  - Pre-commit: `pytest tests/test_routes_page.py -v`

- [x] 18. **Routes - POST /api/scrape + GET /api/scrape/{id}/stream + POST /api/scrape/{id}/cancel**

  **What to do**:
  - Add to `app/routes/api.py`:
    - `POST /api/scrape` (body: `ScrapeRequest`): validates request, creates `ScrapeJob` row (status=pending), schedules `run_scrape_job(job_id, request)` as a background task via `asyncio.create_task` (kept in module-level dict `running_tasks: dict[int, asyncio.Task]`). Returns `{job_id: int, status: "pending"}`. Rejects (409) if active job exists.
    - `GET /api/scrape/{job_id}/stream`: returns `EventSourceResponse` (sse-starlette) that streams events from `event_bus.subscribe(job_id)`. Closes when sentinel received or client disconnects.
    - `POST /api/scrape/{job_id}/cancel`: looks up `running_tasks[job_id]`, calls `.cancel()`. Returns 204.
    - `GET /api/scrape/{job_id}` returns current job status (used for polling fallback).
  - Tests `tests/test_routes_scrape.py`:
    - RED: `test_post_scrape_creates_job_and_returns_id`
    - RED: `test_post_scrape_concurrent_returns_409`
    - RED: `test_get_stream_yields_events_then_completes`
    - RED: `test_post_cancel_sets_job_to_cancelled`
    - RED: `test_post_scrape_invalid_dates_returns_422`

  **Must NOT do**:
  - Do NOT block POST waiting for scrape completion (must return immediately with job_id)
  - Do NOT use `BackgroundTasks` (those run AFTER response and can't be cancelled)
  - Do NOT use threading for the scrape (must be asyncio Task)
  - Do NOT swallow validation errors (let FastAPI return 422)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: SSE + cancellation + concurrency = trio of subtle bugs
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with 17, 19)
  - **Parallel Group**: Wave 3
  - **Blocks**: 21
  - **Blocked By**: 6, 8, 14, 15, 16

  **References**:

  **External References**:
  - sse-starlette EventSourceResponse: `https://github.com/sysid/sse-starlette#example`
  - asyncio.create_task: `https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task`

  **WHY Each Reference Matters**:
  - EventSourceResponse handles SSE protocol details (event:, data:, retry:)
  - create_task gives us a Task handle for cancellation (BackgroundTasks does not)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_routes_scrape.py -v` exits 0 with 5+ passed
  - [ ] No use of `BackgroundTasks` for scraper invocation

  **QA Scenarios**:

  ```
  Scenario: Trigger creates job and returns id immediately
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_scrape.py::test_post_scrape_creates_job_and_returns_id -v
      2. Assert PASS
    Expected Result: 200 with job_id, response time < 200ms
    Failure Indicators: Blocks until scrape completes
    Evidence: .sisyphus/evidence/task-18-trigger.txt

  Scenario: SSE stream yields events from event bus
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_scrape.py::test_get_stream_yields_events_then_completes -v
      2. Assert PASS
    Expected Result: Stream yields ProgressEvent JSON, terminates on done event
    Failure Indicators: Hangs, missing events
    Evidence: .sisyphus/evidence/task-18-stream.txt

  Scenario: Cancel transitions job to cancelled status
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_scrape.py::test_post_cancel_sets_job_to_cancelled -v
      2. Assert PASS
    Expected Result: 204; subsequent GET shows status=cancelled
    Failure Indicators: 200/500, status stuck on running
    Evidence: .sisyphus/evidence/task-18-cancel.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-18-trigger.txt`
  - [ ] `.sisyphus/evidence/task-18-stream.txt`
  - [ ] `.sisyphus/evidence/task-18-cancel.txt`
  - [ ] `.sisyphus/evidence/task-18-pytest.txt`

  **Commit**: YES
  - Message: `feat(api): scrape trigger and sse stream endpoints`
  - Files: `app/routes/api.py` (updated), `tests/test_routes_scrape.py`
  - Pre-commit: `pytest tests/test_routes_scrape.py -v`

- [x] 19. **Routes - GET /api/visits + GET /api/recap**

  **What to do**:
  - Add to `app/routes/api.py`:
    - `GET /api/visits?tanggal_from=&tanggal_to=&ruang=`: returns `list[VisitOut]` (with treatments). Default: today only, all ruang. Max range 31 days (validate).
    - `GET /api/recap?limit=50`: returns `list[RecapOut]` ordered by `tanggal_kunjungan` DESC.
    - `GET /api/recap/{tanggal}` (YYYY-MM-DD): returns single `RecapOut` or 404.
  - Tests `tests/test_routes_data.py`:
    - RED: `test_get_visits_default_today_returns_empty_list`
    - RED: `test_get_visits_with_seed_data_returns_filtered`
    - RED: `test_get_recap_returns_ordered_desc_with_limit`
    - RED: `test_get_recap_by_date_404_when_missing`

  **Must NOT do**:
  - Do NOT return raw ORM objects (use `from_attributes` Pydantic conversion)
  - Do NOT support arbitrary filter operators (only date range + ruang exact match)
  - Do NOT paginate visits in v1 (max 31 days × ~50 per day = <1500 rows, fine)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Read-only endpoints but must align serialization correctly
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with 17, 18)
  - **Parallel Group**: Wave 3
  - **Blocks**: 20
  - **Blocked By**: 6, 8, 16

  **References**:

  **External References**:
  - FastAPI response_model: `https://fastapi.tiangolo.com/tutorial/response-model/`

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_routes_data.py -v` exits 0 with 4+ passed
  - [ ] All decimal fields serialized as strings (not float)

  **QA Scenarios**:

  ```
  Scenario: Visits filtered by date and ruang return correct rows
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_data.py::test_get_visits_with_seed_data_returns_filtered -v
      2. Assert PASS
    Expected Result: Only matching rows returned
    Failure Indicators: Returns all rows
    Evidence: .sisyphus/evidence/task-19-visits.txt

  Scenario: Recap list ordered DESC by date
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_routes_data.py::test_get_recap_returns_ordered_desc_with_limit -v
      2. Assert PASS
    Expected Result: Newest dates first, count <= limit
    Failure Indicators: ASC order, exceeds limit
    Evidence: .sisyphus/evidence/task-19-recap.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-19-visits.txt`
  - [ ] `.sisyphus/evidence/task-19-recap.txt`
  - [ ] `.sisyphus/evidence/task-19-pytest.txt`

  **Commit**: YES
  - Message: `feat(api): visits and recap history endpoints`
  - Files: `app/routes/api.py` (updated), `tests/test_routes_data.py`
  - Pre-commit: `pytest tests/test_routes_data.py -v`

- [x] 20. **Jinja2 templates - base + index + partials**

  **What to do**:
  - Create `templates/base.html`: HTML5 doctype, `<head>` with title "Rekap-In | Puskesmas Baruharjo", links `static/css/output.css`, defers `static/js/app.js`. Body contains `{% block content %}`. Include simple header with app name + small status indicator slot.
  - Create `templates/index.html` extending `base.html` with:
    - **Hero/header**: "Rekap-In" title, subtitle "Rekap Pasien Harian"
    - **Card 1: Filter Form**:
      - Toggle (radio buttons): "Tanggal Tunggal" | "Rentang Tanggal"
      - Date input(s): single date (default today) OR from/to dates
      - Select dropdown: "Pilih Ruang" (populated by JS from /api/ruang); option "Semua Ruang"
      - Buttons: "Mulai Scraping" (primary) | "Batalkan" (danger, disabled by default)
    - **Card 2: Progress**: Hidden by default. Shows: status pill (pending/running/done/error/cancelled), progress bar (current/total), latest log message, elapsed time.
    - **Card 3: Hasil Pasien (Table)**: columns: No RM | Nama | Tgl Lahir | Ruang | Tindakan (collapsible list) | Total Biaya | Tgl Kunjungan. Empty state: "Belum ada data. Klik 'Mulai Scraping' untuk memulai."
    - **Card 4: Riwayat (History)**: list of recap rows: tanggal | total nominal (Rp formatted) | last scraped (relative time). Click row → loads visits for that date into Card 3. Empty state: "Belum ada riwayat."
    - **Footer**: small disabled "Ekspor Excel" button with tooltip "Akan tersedia di versi berikutnya"
  - Create partials:
    - `templates/partials/_progress.html` (rendered into Card 2)
    - `templates/partials/_visit_row.html` (single row in patient table)
    - `templates/partials/_recap_row.html` (single row in history)
  - Use Tailwind classes from Task 3 (`btn-primary`, `card`, etc.)
  - Use Indonesian copy throughout (UI is for Indonesian medical staff)

  **Must NOT do**:
  - Do NOT include English text in user-facing copy
  - Do NOT add "Coming soon" alerts beyond the disabled Excel button
  - Do NOT inline styles (all classes from Tailwind output.css)
  - Do NOT add navigation links to other pages (single-page app for v1)
  - Do NOT add a sidebar (clean single-column flow)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI design judgment, layout, copy, accessibility
  - **Skills**: `[frontend-ui-ux]`
    - `frontend-ui-ux`: Card layout, empty states, progress UI, Indonesian medical context

  **Parallelization**:
  - **Can Run In Parallel**: NO (precedes JS task 21)
  - **Parallel Group**: Wave 3
  - **Blocks**: 21
  - **Blocked By**: 3, 17, 19

  **References**:

  **External References**:
  - Tailwind components inspiration: `https://tailwindui.com/components/application-ui/data-display/description-lists` (free preview)
  - Jinja2 inheritance: `https://jinja.palletsprojects.com/en/3.1.x/templates/#template-inheritance`

  **Acceptance Criteria**:
  - [ ] All template files exist
  - [ ] `python -c "from jinja2 import Environment, FileSystemLoader; e=Environment(loader=FileSystemLoader('templates')); e.get_template('index.html').render(ruang_list=['A','B'], today='2026-05-16')"` exits 0
  - [ ] All user-visible copy in Bahasa Indonesia

  **QA Scenarios**:

  ```
  Scenario: Index page renders with all 4 cards
    Tool: Playwright (skill)
    Preconditions: App running locally
    Steps:
      1. Navigate to http://127.0.0.1:8000/
      2. Assert title contains "Rekap-In"
      3. Assert visible: ".card" count >= 4
      4. Assert visible: button containing "Mulai Scraping"
      5. Assert visible: button "Ekspor Excel" but disabled (button[disabled])
      6. Screenshot full page
    Expected Result: All 4 cards present, primary button visible, Excel disabled
    Failure Indicators: Missing card, primary button absent, Excel enabled
    Evidence: .sisyphus/evidence/task-20-index.png

  Scenario: Date toggle switches between single and range mode
    Tool: Playwright
    Steps:
      1. On index page, assert single-date input visible
      2. Click radio "Rentang Tanggal"
      3. Assert from/to date inputs visible
      4. Click radio "Tanggal Tunggal"
      5. Assert single-date input visible again
    Expected Result: Toggle correctly swaps inputs
    Failure Indicators: Both visible, neither visible
    Evidence: .sisyphus/evidence/task-20-toggle.png
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-20-index.png`
  - [ ] `.sisyphus/evidence/task-20-toggle.png`

  **Commit**: YES
  - Message: `feat(ui): jinja templates for index page and partials`
  - Files: `templates/base.html`, `templates/index.html`, `templates/partials/*.html`
  - Pre-commit: Jinja syntax check via Python import

- [x] 21. **Frontend JS - SSE consumer + table updater + form**

  **What to do**:
  - Create `static/js/app.js` (vanilla, no framework):
    - On DOMContentLoaded: load `/api/ruang` → populate ruang select
    - Toggle handler: switch single/range date inputs
    - Form submit: POST `/api/scrape` with body `{mode, tanggal_from, tanggal_to, ruang}` → on success, store `job_id`, open `EventSource('/api/scrape/{id}/stream')`, show progress card, disable submit, enable cancel
    - SSE `onmessage`: parse JSON `ProgressEvent`, dispatch on `event_type`:
      - `log`: append message to log area
      - `progress`: update progress bar
      - `row`: prepend visit row to table (live preview)
      - `done`: hide progress card, show toast success, refresh history, refresh visits
      - `error`: show error toast with message
      - `cancelled`: show neutral toast "Scraping dibatalkan"
    - Cancel button: POST `/api/scrape/{id}/cancel`
    - History row click: fetch `/api/visits?tanggal_from=X&tanggal_to=X` → re-render table
    - Number formatting: `Intl.NumberFormat('id-ID', {style:'currency', currency:'IDR', minimumFractionDigits:0})`
    - Date formatting: relative time helper for "5 menit lalu" (Indonesian)
  - Create `static/js/format.js` with pure helpers (currency, date) — easy unit test
  - Tests `tests/test_format.js`: skip JS tests (no Node in this stack); instead `tests/test_format_helpers.py` validates equivalent Python helpers used in templates if applicable. Skip pure-JS tests for v1 (manual QA covers it).

  **Must NOT do**:
  - Do NOT add a JS framework (React/Vue) — keep vanilla
  - Do NOT bundle/transpile (target modern browsers, ES2020+)
  - Do NOT poll status endpoint (use SSE)
  - Do NOT use jQuery
  - Do NOT introduce TypeScript build pipeline

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Frontend logic + UX wiring; needs SSE handling + form interactions discipline
  - **Skills**: `[frontend-ui-ux]`
    - `frontend-ui-ux`: Toast notifications, loading states, accessible UX

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on 20)
  - **Parallel Group**: Wave 3
  - **Blocks**: 22
  - **Blocked By**: 14, 18, 20

  **References**:

  **External References**:
  - EventSource API: `https://developer.mozilla.org/en-US/docs/Web/API/EventSource`
  - Intl.NumberFormat IDR: `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat`

  **WHY Each Reference Matters**:
  - EventSource auto-reconnects (good for resilience)
  - IDR formatter handles thousands separator and Rp prefix per Indonesian locale

  **Acceptance Criteria**:
  - [ ] `static/js/app.js` and `static/js/format.js` exist
  - [ ] No `import React` / `import Vue` / jQuery
  - [ ] Manual QA via Playwright verifies form submit and SSE event flow

  **QA Scenarios**:

  ```
  Scenario: Form submit triggers scrape, SSE shows progress, table updates
    Tool: Playwright (skill)
    Preconditions: App running with mocked EMR (file:// fixture)
    Steps:
      1. Navigate to http://127.0.0.1:8000/
      2. Wait for ruang select to populate
      3. Choose "Tanggal Tunggal", set today's date
      4. Choose "Poli Umum" from ruang dropdown
      5. Click "Mulai Scraping"
      6. Wait for progress card visible (timeout 5s)
      7. Wait for at least one log entry visible
      8. Wait for "done" toast (timeout 30s)
      9. Assert visit table has rows
      10. Screenshot evidence
    Expected Result: Full happy-path flow with live updates
    Failure Indicators: Progress never appears, table empty after done
    Evidence: .sisyphus/evidence/task-21-flow.png

  Scenario: Cancel button stops scrape mid-way
    Tool: Playwright
    Steps:
      1. Trigger scrape on a date with many patients
      2. Wait for progress card visible
      3. Click "Batalkan"
      4. Wait for "Scraping dibatalkan" toast
      5. Assert progress card hidden
    Expected Result: Cancellation transition successful
    Failure Indicators: Cancel ignored, scrape continues
    Evidence: .sisyphus/evidence/task-21-cancel.png

  Scenario: Currency formatted as IDR
    Tool: Playwright
    Steps:
      1. After scrape with mock data, inspect "Total Biaya" cell
      2. Assert text matches /Rp\s?[\d.]+/
    Expected Result: e.g., "Rp 250.000"
    Failure Indicators: "$ 250000" or "250000.0"
    Evidence: .sisyphus/evidence/task-21-currency.png
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-21-flow.png`
  - [ ] `.sisyphus/evidence/task-21-cancel.png`
  - [ ] `.sisyphus/evidence/task-21-currency.png`

  **Commit**: YES
  - Message: `feat(ui): frontend js with sse consumer and table updater`
  - Files: `static/js/app.js`, `static/js/format.js`
  - Pre-commit: manual QA passing

- [x] 22. **End-to-end wiring + recap upsert logic**

  **What to do**:
  - Verify orchestrator (T15) calls `recap_repo.upsert_recap` with computed totals after each date completes
  - Add reconciliation: after upsert_visit, recompute recap totals from current visits in DB (not from accumulator) — defends against partial failures
  - Verify cancel flow: orchestrator catches CancelledError → status=cancelled → still upserts recap for fully-completed dates only (not partial dates)
  - Verify re-scrape flow: same date triggered twice → upsert_visit replaces treatments → recap.last_scraped_at advances → no duplicate recap rows
  - Add an integration test `tests/test_e2e.py` (uses real SQLite + mocked Playwright):
    - RED: `test_e2e_full_happy_path` (POST /api/scrape → poll until done → GET /api/visits + /api/recap → verify counts)
    - RED: `test_e2e_rescrape_updates_recap_not_duplicates`
    - RED: `test_e2e_cancel_partial_persistence`
    - RED: `test_e2e_session_expiry_recovers`
  - Update `README.md` with quickstart + troubleshooting (e.g., "If login fails, re-run discovery script")

  **Must NOT do**:
  - Do NOT introduce new modules (only wiring + tests + docs)
  - Do NOT relax existing tests
  - Do NOT add real EMR network calls in CI tests

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration verification + reconciliation logic + edge case proofing
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (last task in Wave 3)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: 5, 8, 15, 17, 18, 19, 20, 21

  **References**:

  **Pattern References**:
  - All previous tasks (this is the integration task)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_e2e.py -v` exits 0 with 4+ passed
  - [ ] `pytest tests/ -v` (full suite) exits 0
  - [ ] `ruff check .` clean
  - [ ] `mypy app scraper models config --ignore-missing-imports` clean
  - [ ] README quickstart accurate

  **QA Scenarios**:

  ```
  Scenario: Full E2E happy path with mocked EMR
    Tool: Bash
    Preconditions: Mock EMR fixture loaded
    Steps:
      1. Run: pytest tests/test_e2e.py::test_e2e_full_happy_path -v
      2. Assert PASS
    Expected Result: Visits + recap + job rows populated; status=done
    Failure Indicators: Missing data, wrong totals
    Evidence: .sisyphus/evidence/task-22-e2e-happy.txt

  Scenario: Re-scrape updates recap, no duplicates
    Tool: Bash
    Steps:
      1. Run: pytest tests/test_e2e.py::test_e2e_rescrape_updates_recap_not_duplicates -v
      2. Assert PASS
    Expected Result: Single recap row per date, last_scraped_at updated
    Failure Indicators: Duplicate recap rows
    Evidence: .sisyphus/evidence/task-22-rescrape.txt

  Scenario: Full test suite + lint + type checks pass
    Tool: Bash
    Steps:
      1. Run: pytest tests/ -v 2>&1 | Tee-Object .sisyphus/evidence/task-22-pytest.txt
      2. Run: ruff check . 2>&1 | Tee-Object .sisyphus/evidence/task-22-ruff.txt
      3. Run: mypy app scraper models config --ignore-missing-imports 2>&1 | Tee-Object .sisyphus/evidence/task-22-mypy.txt
      4. Assert all 3 exit 0
    Expected Result: Clean codebase
    Failure Indicators: Failures, lint warnings, type errors
    Evidence: .sisyphus/evidence/task-22-pytest.txt, .sisyphus/evidence/task-22-ruff.txt, .sisyphus/evidence/task-22-mypy.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-22-e2e-happy.txt`
  - [ ] `.sisyphus/evidence/task-22-rescrape.txt`
  - [ ] `.sisyphus/evidence/task-22-pytest.txt`
  - [ ] `.sisyphus/evidence/task-22-ruff.txt`
  - [ ] `.sisyphus/evidence/task-22-mypy.txt`

  **Commit**: YES
  - Message: `feat(integration): end-to-end wiring and recap upsert logic`
  - Files: `tests/test_e2e.py`, `README.md` (updated), small fixes to orchestrator/repos as needed
  - Pre-commit: full pytest + ruff + mypy clean

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback → fix → re-run → present again → wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`

  Read this plan end-to-end. For each "Must Have": verify implementation exists by reading the file or running the command. For each "Must NOT Have": search the codebase for the forbidden pattern — reject with `file:line` if found (especially: Excel logic, hardcoded selectors, PII in logs, `time.sleep`, `as Any`, generic names). Check that ALL evidence files in `.sisyphus/evidence/task-*` exist. Compare deliverables list against actual files.

  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | Evidence [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`

  Run `pytest tests/ -v` (must pass), `ruff check .` (must be clean), `mypy app scraper models config --ignore-missing-imports` (must be clean). Review every changed `.py` file for: `as Any`, `# type: ignore` without justification, empty `except:`, `print()` in non-test code, commented-out code blocks, unused imports, generic names (`data`, `result`, `item`, `temp`, `helper`). Check AI slop: excessive comments stating the obvious, premature abstractions (BaseScraper/AbstractStorage with single impl), 10+ line docstrings on 3-line functions.

  Output: `Tests [N pass / N fail] | Lint [PASS/FAIL] | Types [PASS/FAIL] | Files [N clean / N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` + `playwright` skill

  Start fresh: delete `rekap_in.db`, kill any running uvicorn. Run `python -m app`. Use Playwright to: (1) navigate to `http://127.0.0.1:8000`, (2) verify page loads with form elements, (3) select date + ruang, (4) click "Mulai Scraping" with mocked EMR (env `EMR_BASE_URL=file://tests/fixtures/emr/index.html`), (5) verify SSE progress events stream, (6) verify table populated, (7) verify history record created, (8) re-trigger same date, verify history record UPDATED (not duplicated), (9) test cancel button mid-scrape. Test edge cases: empty result, login failure, selector miss. Save evidence to `.sisyphus/evidence/final-qa/`.

  Output: `UI Loads [PASS/FAIL] | Form [PASS/FAIL] | Scrape Flow [PASS/FAIL] | SSE [PASS/FAIL] | Table [PASS/FAIL] | History Upsert [PASS/FAIL] | Cancel [PASS/FAIL] | Edge Cases [N pass/N fail] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`

  For each task 1-22: read "What to do" section in this plan, then read git diff for that task's files. Verify 1:1: every spec'd item built, nothing beyond spec built. Specifically check: (a) Excel export NOT implemented (only placeholder), (b) NO multi-user auth, (c) NO scheduler/cron, (d) NO real EMR test against live site. Detect cross-task contamination: Task N modifying files owned by Task M. Flag any file in `git status` not accounted for in any task.

  Output: `Tasks [N/N compliant] | Excluded items [VERIFIED ABSENT] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

Each task ends with one commit (Conventional Commits format). Sample messages:

| Task | Message |
|---|---|
| 1 | `chore(scaffold): initial project structure with .env.example and requirements` |
| 2 | `chore(test): pytest infrastructure with async support` |
| 3 | `chore(ui): tailwind cli setup with base styles` |
| 4 | `feat(config): env loader and selectors yaml schema` |
| 5 | `feat(models): sqlalchemy models for visit, treatment, job, recap` |
| 6 | `feat(schemas): pydantic dtos for api contracts` |
| 7 | `docs(scraper): emr selector discovery and documentation` |
| 8 | `feat(db): async session and repository layer` |
| 9 | `feat(scraper): playwright browser context manager` |
| 10 | `feat(scraper): login flow with select2 and credentials` |
| 11 | `feat(scraper): navigation to pendaftaran induk page` |
| 12 | `feat(scraper): emr filter for date and ruang` |
| 13 | `feat(scraper): row extraction with click-per-row strategy` |
| 14 | `feat(progress): in-memory sse event bus` |
| 15 | `feat(scraper): job orchestrator state machine` |
| 16 | `feat(api): fastapi app skeleton with lifespan` |
| 17 | `feat(api): index page and ruang list endpoint` |
| 18 | `feat(api): scrape trigger and sse stream endpoints` |
| 19 | `feat(api): visits and recap history endpoints` |
| 20 | `feat(ui): jinja templates for index page and partials` |
| 21 | `feat(ui): frontend js with sse consumer and table updater` |
| 22 | `feat(integration): end-to-end wiring and recap upsert logic` |

Pre-commit checks for each: `pytest -q && ruff check . && mypy app scraper models config --ignore-missing-imports`.

---

## Success Criteria

### Verification Commands

```bash
# Setup verification
python -m pip install -r requirements.txt
python -m playwright install chromium
ls -la .env.example .gitignore requirements.txt pyproject.toml  # all exist

# Test verification
pytest tests/ -v                                                # all pass
pytest tests/ --cov=app --cov=scraper --cov=models --cov=config # coverage report
ruff check .                                                    # clean
mypy app scraper models config --ignore-missing-imports         # clean

# App verification (with mock EMR)
EMR_BASE_URL=file://tests/fixtures/emr/index.html python -m app &
sleep 3
curl -s http://127.0.0.1:8000/ | grep -q "Rekap-In"             # returns 0
curl -s http://127.0.0.1:8000/api/ruang | python -m json.tool   # returns ruang list
sqlite3 rekap_in.db "SELECT COUNT(*) FROM scrape_jobs;"         # 0 initially
```

### Final Checklist
- [ ] All "Must Have" items implemented and verified
- [ ] All "Must NOT Have" items explicitly absent (verified by F1)
- [ ] All 22 implementation tasks completed with evidence files
- [ ] All F1-F4 verification agents APPROVE
- [ ] User explicitly says "okay" to mark plan complete
