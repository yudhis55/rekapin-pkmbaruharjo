# Learnings


## Task 15 - Scrape Job Orchestrator (2026-05-16)

### What Was Done
- Created `scraper/orchestrator.py` — state machine tying login → nav → filter → extract → persist → upsert recap
- Created `tests/test_orchestrator.py` with 5 tests (happy path, session expiry retry, login error, concurrent rejection, cancellation)
- Evidence saved to `.sisyphus/evidence/task-15-pytest.txt`

### Results
- 5/5 tests PASSED (0.81s)

### Key Patterns
- `_running_tasks` dict at module level tracks asyncio.Task per job_id for cancellation support
- `_scrape_one_date` recursive retry: on SessionExpiredError, calls itself once with `retry_on_session_expired=False`
- Browser context opened fresh per date for isolation (range mode loops dates)
- `get_active_job()` uses `scalar_one_or_none()` — test must ensure only ONE job is in PENDING/RUNNING state when testing concurrent rejection
- `asyncio.CancelledError` is re-raised after marking job cancelled (required for proper task cleanup)
- `event_bus.close(job_id)` in `finally` block ensures SSE subscriber gets sentinel even on error paths

### Test Gotcha
- `job_repo.get_active_job` queries for PENDING or RUNNING status — creating a second job via `create_job` (which defaults to PENDING) causes `MultipleResultsFound`. Fix: mark the second job as ERROR before calling `run_scrape_job` so only the first job is "active".


## Task 16 - FastAPI App Skeleton (2026-05-16)

### What Was Done
- Created `app/main.py` with `create_app()` factory, lifespan, static mount, Jinja2 templates, and exception handlers
- Created `app/__main__.py` entrypoint for `python -m app`
- Created `tests/test_app.py` with 4 tests
- Evidence saved to `.sisyphus/evidence/task-16-pytest.txt`

### Results
- 4/4 tests PASSED (1.14s)

### Key Patterns
- `create_app()` factory pattern (not module-level `app = FastAPI()`) enables clean test isolation — each test gets a fresh app instance
- `lifespan` asynccontextmanager replaces deprecated `@app.on_event` — `await init_db()` on startup, log on shutdown
- Static mount guarded by `STATIC_DIR.exists()` — no crash if `static/` absent in CI
- `templates = Jinja2Templates(...)` at module level so routes can import it directly
- Exception handlers registered inside `create_app()` so they're scoped to the factory instance
- CORS intentionally omitted — single-origin local app, no cross-origin needed

### Test Patterns
- `_setup_env` autouse fixture: sets env vars, clears `get_settings` lru_cache, resets `_engine`/`_sessionmaker` to None before and after each test
- `TestClient(app)` as context manager drives lifespan (startup + shutdown)
- Exception handler tested by including a throwaway `APIRouter` with a route that raises the target exception
- `get_settings.cache_clear()` required after `monkeypatch.setenv` — otherwise cached Settings from a prior test bleeds in


## Task 5 - SQLAlchemy 2.x Async Models (2026-05-16)

### What Was Done
- Created `models/base.py` with `Base` (DeclarativeBase) and `TimestampMixin`
- Created `models/job.py` with `ScrapeJob` + `JobStatus` enum
- Created `models/visit.py` with `PatientVisit` + UniqueConstraint
- Created `models/treatment.py` with `Treatment` (CASCADE FK to patient_visits)
- Created `models/recap.py` with `DailyRecap` (unique per tanggal_kunjungan)
- Created `models/__init__.py` re-exporting all models
- Created `tests/test_models.py` with 5 TDD tests
- Evidence saved to `.sisyphus/evidence/task-5-pytest.txt`

### Results
- 5/5 tests PASSED (0.62s)
- Zero `Float`/`Real` usage — all monetary fields use `Numeric(15, 2)`

### SQLAlchemy 2.x Async Quirks
- `asyncio_mode = "auto"` in pyproject.toml means no `@pytest.mark.asyncio` needed
- `async_sessionmaker` (not `sessionmaker`) required for async sessions
- `expire_on_commit=False` on async sessionmaker avoids lazy-load errors after commit — attributes remain accessible without re-querying
- `engine.begin()` for DDL (`create_all`), `async_sessionmaker()` for DML
- `TYPE_CHECKING` guard on cross-model imports prevents circular import errors at runtime while keeping type hints intact
- `Mapped[T | None]` with `nullable=True` is the 2.0 pattern; avoid legacy `Optional[T]` + `Column()`
- SQLite doesn't enforce `Enum` at DB level — validation happens in Python layer only
- `ondelete="CASCADE"` on FK is DB-level; `cascade="all, delete-orphan"` on relationship is ORM-level — both needed for full cascade behavior
- `server_default=func.now()` sets DB-side default; `default=` sets Python-side default — use `server_default` for timestamps to avoid timezone drift


## Task 7 - EMR Site Discovery (2026-05-16)

### What Was Done
- Created `discovery/capture_flow.py` — reusable Playwright script for EMR flow capture
- Captured 4 HTML + 4 PNG fixtures (anonymized) in `tests/fixtures/emr/`
- Updated `config/selectors.yaml` with all real selectors (zero TODO_DISCOVER remaining)
- Created `docs/EMR-FLOW.md` with full flow documentation

### Key Discoveries

#### Login
- Form: `form[name='form']` POST to `/daf`
- Puskesmas: `select[name='id_cabang']` (Select2 over native) — value `16` = BARUHARJO
- Username: `input[name='user']`, Password: `input[name='pass']`
- Submit: `input[name='submit'][value='Login']`
- Hidden field `input[name='login']` required
- CSRF token per-form: `input[name='csrf_token_name']`
- **Strategy**: Use native `select_option()` — bypasses Select2 JS reliably

#### Navigation
- Post-login URL stays at `/daf` (same URL, different content)
- "PENDAFTARAN INDUK" link → `/daf/px/1/1/0/0`

#### Patient List (`/daf/px/1/{page}/0/0`)
- Date filter: `input[name='tanggal'][type='date']` (YYYY-MM-DD)
- Ruang filter: `select[name='id_ruangx']` (native, 24 options)
- Search button: `button[title='cari']`
- Patient table: `table.table-sm.table-bordered.table-hover.small`
- **NO pagination** — all daily patients shown at once (29 rows observed)
- No `<th>` headers — columns inferred from labeled `<td>` row

#### Patient Row Structure
- Columns: No, No.RM, Nama, Tgl Lahir, Alamat, L/P, Asuransi, Edit Pasien, DATA KUNJUNGAN
- Actions are form POSTs (not links): Resume, CPPT, Edit, Daftar, Pindah, Bayar, RM
- Kunjungan data is INLINE nested table (Ruangan, Cara Bayar, Tgl.Masuk, Batal)

#### Detail Access
- **Type: NEW PAGE via form POST** (not modal, not inline)
- CPPT: `/rp/res/{visit_id}/0/0`
- RM: `/daf/px/30/1/{rm_id}/{visit_id}`
- Bayar: `/daf/px/20/1/0/{visit_id}`
- Each form has its own CSRF token — must extract per-form before POST

### Gotchas
- CSRF tokens regenerate on every page load — cannot cache/reuse
- Playwright `executable_path` needed: chromium-1169 installed, pip expects 1217
- CI4 debug toolbar adds extra `<table>` elements — filter by class when scraping
- Date display format differs: input=YYYY-MM-DD, display=DD-MM-YYYY HH:MM
- `04-detail-page-or-modal` capture went back to dashboard (clicked wrong link) — detail requires form POST, not GET

### Chromium Version Issue
- Playwright pip package 1.59.0 expects chromium-1217
- Only chromium-1169 installed at `C:\Users\Yudhistira\AppData\Local\ms-playwright\chromium-1169\chrome-win\chrome.exe`
- Workaround: use `executable_path` parameter in `launch()`
- `playwright install chromium` timed out (>180s) — may need manual retry


## Task 8 - Async DB Session Manager + Repository Layer (2026-05-16)

### What Was Done
- Created `app/db/__init__.py`, `app/db/session.py`, `app/db/init_db.py`
- Created `app/db/repositories/visit_repo.py`, `job_repo.py`, `recap_repo.py`
- Created `tests/test_repositories.py` with 5 TDD tests
- Evidence saved to `.sisyphus/evidence/task-8-pytest.txt`

### Results
- 5/5 tests PASSED (0.69s)

### SQLAlchemy Upsert Patterns

- **Upsert via select-then-insert**: No native `INSERT OR REPLACE` needed — query by unique key, branch on `None`. Cleaner than `on_conflict_do_update` for ORM-level relationship management.
- **Replacing child collections**: `existing.treatments.clear()` + `append()` leverages `cascade="all, delete-orphan"` — SQLAlchemy issues DELETEs for removed children automatically on flush.
- **`selectinload` on upsert**: Load the relationship eagerly in the select query so `.treatments` is populated before `.clear()` — avoids `MissingGreenlet` / lazy-load errors in async context.
- **`session.refresh(visit, attribute_names=["treatments"])`**: After commit, refresh only the relationship to avoid re-fetching the whole object; keeps the returned object fully populated.
- **`update()` for status transitions**: Use `sqlalchemy.update()` (core-style) for targeted field updates (status, timestamps) without loading the full ORM object — more efficient for fire-and-forget state changes.
- **`func.coalesce(func.sum(...), 0)`**: Handles the empty-table case where `SUM` returns `NULL`; without coalesce, `Decimal(str(None))` raises `TypeError`.
- **Global singleton engine/sessionmaker**: Module-level `_engine`/`_sessionmaker` with lazy init via `get_engine()` / `get_sessionmaker()` — tests override by calling `make_engine(url)` directly, bypassing the singleton.
- **`asyncio_mode = "auto"`**: No `@pytest.mark.asyncio` needed; all `async def test_*` functions are picked up automatically.

## Task 6 - Pydantic v2 DTOs (2026-05-16)

### What Was Done
- Created `app/schemas/__init__.py` (package marker)
- Created `app/schemas/dto.py` with 6 DTOs: `ScrapeRequest`, `TreatmentOut`, `VisitOut`, `RecapOut`, `ScrapeJobOut`, `ProgressEvent`
- Created `tests/test_schemas.py` with 6 tests covering validation logic
- Evidence saved to `.sisyphus/evidence/task-6-pytest.txt`

### Results
- 6/6 tests PASSED (0.26s)
- Zero `float` usage — all monetary fields use `Decimal`

### Notes
- `model_validator(mode="after")` used for cross-field date validation in `ScrapeRequest`
- `field_validator` on `ProgressEvent.event_type` is redundant with `Literal` type but kept per spec
- `ConfigDict(from_attributes=True)` on all `*Out` models enables ORM → schema conversion
- `T | None` union syntax used throughout (Python 3.10+ style, no `Optional`)
- 31-day range limit: delta = `(to - from).days`, so 31 days apart = 32 calendar days → raises error


### What Was Done
- Created `tests/conftest.py` with session-scoped `event_loop`, placeholder `db_session`, and `mock_env` fixtures
- Created `tests/test_smoke.py` with 2 smoke tests: `test_python_version` and `test_event_loop_runs`
- Created `tests/fixtures/__init__.py` (package marker) and `tests/fixtures/.gitkeep` (placeholder)
- Verified `pyproject.toml` already had `asyncio_mode = "auto"` — no conflicts

### Results
- Both smoke tests PASSED (pytest 9.0.3, Python 3.11.3, asyncio mode=AUTO)
- Evidence saved to `.sisyphus/evidence/task-2-smoke-output.txt`

### Notes
- `asyncio_mode = "auto"` means no `@pytest.mark.asyncio` decorator needed on async test functions
- `event_loop` fixture is session-scoped to share across tests — avoids loop-per-test overhead
- `db_session` yields `None` as placeholder; Task 5/8 will provide real implementation
- `tests/fixtures/` directory is reserved for HTML fixtures (Task 7 populates)


### What Was Done
- Created full directory tree: app/, scraper/, models/, config/, templates/, static/css/, static/js/, tests/, tests/fixtures/emr/, exports/, tools/, discovery/, docs/
- Created: requirements.txt, requirements-dev.txt, pyproject.toml, .env.example, .env, .gitignore, README.md
- Created empty `__init__.py` (with `# Package marker`) in: app/, scraper/, models/, config/, tests/

### Conventions Established
- Python 3.11 target
- ruff line-length = 100, select = ["E","F","I","N","W"]
- mypy strict = true
- pytest asyncio_mode = "auto"
- SQLite via aiosqlite (DATABASE_URL=sqlite+aiosqlite:///./rekap_in.db)
- Playwright browser: chromium, headless by default

### Key Paths
- App entry: `python -m app`
- Dev server: http://127.0.0.1:8000
- DB file: rekap_in.db (gitignored)
- Exports: exports/*.xlsx (gitignored)

### Notes
- .env is identical to .env.example — user must fill EMR_USERNAME and EMR_PASSWORD
- No frontend files yet (Task 3 owns static/css, static/js)
- No selectors.yaml yet (Task 4 owns that)

## Task 3 - Tailwind CSS v4 Standalone CLI (2026-05-16)

### What Was Done
- Downloaded Tailwind standalone CLI binary: `tools/tailwindcss.exe` (v4.3.0, 125MB)
- Created `static/css/input.css` using v4 syntax (`@import "tailwindcss"` + `@theme {}`)
- Created `tailwind.config.js` (v4 ignores it — kept for reference only)
- Created `tools/build-css.ps1` and `tools/watch-css.ps1`
- Generated `static/css/output.css` (8,932 bytes, minified)
- Evidence saved to `.sisyphus/evidence/task-3-build.txt`

### Results
- Build: Done in 114ms
- Output: 8.9KB, contains `.btn-primary` ✓

### Tailwind v4 Breaking Changes vs v3
- `tailwind.config.js` is IGNORED in v4 — theme is defined in CSS via `@theme {}` block
- `@tailwind base/components/utilities` directives are GONE — replaced by `@import "tailwindcss"`
- `@apply` with custom color tokens (e.g. `bg-ink-50`) fails unless tokens are defined via `@theme` — use plain CSS properties instead in `@layer components`
- Content paths auto-detected in v4; no `content: []` config needed
- Custom colors use `--color-*` CSS variable naming convention in `@theme`
- Custom fonts use `--font-family-*` in `@theme`

## Task 4 - Config Module (2026-05-16)

### What Was Done
- Created `config/settings.py` - Pydantic BaseSettings with SecretStr for credentials
- Created `config/ruang.py` - hardcoded placeholder RUANG_LIST (9 entries)
- Created `config/selectors.yaml` - placeholder YAML schema (all values "TODO_DISCOVER")
- Created `config/selectors.py` - Pydantic models + lru_cache loader for selectors.yaml
- Created `tests/test_config.py` - 6 TDD tests, all PASSED

### Results
- 6/6 tests passed in 0.34s
- Evidence saved to `.sisyphus/evidence/task-4-pytest.txt`

### Pydantic-settings v2 Quirks
- `Settings(_env_file=None)` suppresses .env file loading in tests — pass as keyword arg, not positional
- `monkeypatch.setenv` + `_env_file=None` is the correct pattern for isolated unit tests; avoids reading real `.env`
- `lru_cache` on `load_selectors` requires explicit `cache_clear()` between tests that use different YAML paths
- `SecretStr` repr shows `**********` — confirmed redaction works without extra config
- `extra="ignore"` in `SettingsConfigDict` prevents ValidationError on unknown env vars (safe for CI environments with extra vars)




## task-14: EventBus (2026-05-16)
- asyncio_mode=auto in pyproject.toml � async tests work without @pytest.mark.asyncio
- Sentinel pattern (module-level object()) cleanly terminates AsyncIterator without exceptions
- Single-consumer model: subscribe() finally-block pops queue, preventing leaks
- _cleanup_stale() runs on every _get_queue() call � O(n) but acceptable for low job counts
- ProgressEvent fields: event_type (Literal), message, current, total, payload


## Task 9 - Browser Context Manager + Screenshot Helper (2026-05-16)

### Patterns
- syncio_mode = "auto" in pyproject.toml means no @pytest.mark.asyncio needed, but decorators are harmless
- get_settings.cache_clear() required in tests that monkeypatch env vars affecting settings (lru_cache)
- playwright_browser(headless=True) with bout:blank is the correct pattern for unit tests - no real network needed
- context.set_default_timeout(ms) not page.set_default_timeout - set on context level
- try/finally inside asynccontextmanager ensures browser cleanup even on exception

### Playwright Install
- playwright install chromium downloads two binaries: Chrome for Testing (~179MB) + Chrome Headless Shell (~111MB)
- Downloads don't resume from partial - each invocation restarts from 0% but completes faster on subsequent runs (likely cached segments)
- Use 600000ms timeout for install commands on slow connections

### Test Results
- 3/3 passed in 3.72s
- 0 zombie chrome processes after test run - context manager cleanup works correctly

## 2026-05-16 20:21 - EMR Discovery Critical Findings (Task 7)

### Architecture (different from original plan assumptions!)
- Detail is NOT a modal - it's form POST navigation to NEW URLs (CPPT, RM, Bayar pages)
- NO pagination on /daf/px/1/1/0/0 - all patients shown at once for the selected date
- Visit data (Ruangan, Cara Bayar, Tgl Masuk) is INLINE in nested table within each patient row
- Tindakan + biaya require navigating to CPPT/RM detail pages (separate POSTs)

### Required for every form POST
- CSRF token field name: csrf_token_name
- Token is per-form, per-page-load - must be re-extracted before each POST

### Login form
- form name='form', POST to /daf
- Puskesmas: native <select name='id_cabang'> (Select2 wraps it but native select_option works)
- BARUHARJO value = "16"
- Submit: input[name='submit'][value='Login']

### Filter form
- date_filter is type=date with YYYY-MM-DD format
- ruang_filter is native <select name='id_ruangx'> with numeric IDs
- Apply: button[title='cari']
- Form submit (NOT AJAX) - reloads page with filtered results

### Patient row structure
- Each <tr> has nested <table> in last <td> with visit info per row
- Action buttons are <form method='post'> with their own CSRF tokens
- URL patterns documented in docs/EMR-FLOW.md

### Implications for Task 13 (extract)
- "Click row" strategy from plan needs revision - clicking goes to a NEW URL via POST
- Better: stay on list page, parse the inline kunjungan table for Ruangan + Tgl Masuk
- For Tindakan + Biaya: navigate to CPPT/RM detail per row, then go BACK
- Or: re-think and just use the list page data (kunjungan already inline)

## Task 11 - Navigation Module (2026-05-16)
- pytest-asyncio mode=AUTO means no need for explicit @pytest.mark.asyncio decorators (but they don't hurt)
- Playwright route interception on BrowserContext works well for fixture-based tests
- ctx.route('**/*', handler) intercepts all requests including navigation from clicks
- Tests run in ~15s (4 tests) due to Playwright browser startup overhead
- scraper/exceptions.py was already created by Task 10 with all needed classes


## Task 12 - Filter Module (2026-05-16)
- EMR fixture has select[name='id_ruangx'] with all ruang options as <option value="NNN">NAME</option>
- Date input is input[name='tanggal'][type='date'] with YYYY-MM-DD format via isoformat()
- Apply button is utton[title='cari'] which triggers form submit (page reload)
- Playwright select_option(value=...) works with string values matching option value attributes
- expect_navigation handles the form submit reload; fallback waits for patient_table reappear
- pytest-asyncio mode=AUTO means no need for explicit @pytest.mark.asyncio decorator (but it doesn't hurt)
- Test uses ctx.route("**/*", handle) to intercept all requests and serve fixture HTML


## Task 13 - EMR Row Extraction Module (2026-05-16)

### What Was Done
- Created `scraper/types.py` with frozen dataclasses (VisitData, TreatmentData)
- Created `scraper/extract.py` with `extract_visits()` function
- Created `tests/test_extract.py` with 7 TDD tests (5 async + 2 unit)
- Evidence saved to `.sisyphus/evidence/task-13-pytest.txt`

### Results
- 7/7 tests PASSED (8.34s)
- Extracts patient identity + inline visit data from pendaftaran induk page
- Tindakan/biaya stubbed (empty tuple, Decimal("0.00")) - deferred to v2

### Fixture Structure Discoveries
- Patient table class: `table table-sm table-bordered table-hover small` (5 classes, selector `table.table-sm.table-bordered.table-hover.small` works fine)
- First 2 `<tr>` in tbody are header rows (DATA PASIEN/DATA KUNJUNGAN + column headers) - filtered by cell_count < 8
- Patient rows have 10 `<td>` cells (some with colspan)
- No.RM cell (index 1) contains RM number on first line + Resume/CPPT form buttons below
- Nama cell (index 2) contains name on first line + "Gabung" button below
- Tgl Lahir cell (index 3): "DD/MM/YYYY\nAge\n\nBPJS_number"
- Last cell contains nested `<table width="100%" border="1">` with visit rows
- Visit rows: `<tr style="background-color:transparent">` with 4 `<td>` (Ruangan, Cara Bayar, Tgl.Masuk, Batal)
- Ruangan td has its own nested table with room name + "Pindah" button
- Tgl.Masuk format: "DD/MM/YYYY HH:MM" (date parsed, time ignored)
- Dates in fixture are anonymized to 01/01/1990 but parsing works correctly

### Key Design Decisions
- Flat list output (one VisitData per visit, not per patient) - easier for downstream DB upsert
- Per-row error handling: log warning + skip, never abort entire extraction
- PII redaction: `_redact_rm()` shows only first 2 chars in logs; nama never logged
- `is_logged_in()` check works on fixture because URL contains `/daf/px/` and table is present
- Progress callback fires (0, total, "starting") then (i+1, total, label) per row

### Gotchas
- Header rows in `<tbody>` (not `<thead>`) - must filter by cell count
- Nested tables inside cells mean `inner_text()` captures ALL descendant text including button labels
- "Pindah" button text leaks into ruang extraction - filtered out by splitlines + exclusion
- asyncio_mode=auto in pyproject.toml but tests still need `@pytest.mark.asyncio` decorator (observed in existing tests)

## Task 17 - FastAPI Routes (2026-05-16)
- Circular import avoided by lazy-importing pp.main inside the route function body (import app.main as _main) rather than at module top-level
- Jinja2Templates.TemplateResponse(request, name, context) positional signature works in FastAPI 0.100+
- 	emplates instance lives at module level in pp.main; routes access it via lazy import
- egister_routes() called inside create_app() with a local import to keep pp/routes/__init__.py free of top-level circular deps
- Placeholder 	emplates/index.html renders uang_list, 	oday, pp_title - sufficient for Task 17 tests; Task 20 will replace it

## Task 18 - Scrape routes + SSE (2026-05-16)
- POST /api/scrape: creates job, schedules asyncio.create_task, returns 202 immediately
- GET /api/scrape/{job_id}: status via job_repo.get_job
- GET /api/scrape/{job_id}/stream: SSE via EventSourceResponse + event_bus.subscribe
- POST /api/scrape/{job_id}/cancel: delegates to orchestrator.cancel_job, 404 if not active
- Tests: monkeypatch orchestrator internals (playwright_browser, scraper_login, go_to_pendaftaran_induk, apply_filter, extract_visits) to avoid real browser
- 409 test: seed DB with RUNNING job via get_sessionmaker() + asyncio.get_event_loop().run_until_complete
- sse_starlette.sse.EventSourceResponse works fine with TestClient (sync)
- Import deduplication: combined all imports at top of api.py, no duplicates

## Task 19 - Read-only API routes for visits and recaps (2026-05-16)
- Routes added to existing router in app/routes/api.py - read file first to avoid clobbering parallel task work
- TestClient + asyncio.get_event_loop().run_until_complete() pattern works for seeding async repos in sync tests
- aiosqlite 'Event loop is closed' warning on teardown is benign - 73 passed cleanly
- /api/recap/{tanggal} path param parsed as date directly by FastAPI - no manual parsing needed
- 31-day range guard implemented in endpoint logic (not repo layer)

## Task 20+21 - Frontend Templates & JS (2026-05-16)

### Template structure
- 	emplates/base.html - HTML5 shell; loads output.css, format.js, app.js (defer)
- 	emplates/index.html - extends base; 4 cards: filter, progress, visits, history
- 	emplates/partials/_visit_row.html - server-side partial kept minimal; JS renders rows via innerHTML

### JS architecture
- static/js/format.js - pure helpers exposed as window.RekapFormat; no deps
- static/js/app.js - IIFE; consumes RekapFormat; SSE via EventSource; no framework

### Gotchas
- Radio inputs use peer sr-only pattern (Tailwind peer); Playwright must click the visible <span> label, NOT the hidden input
- data-mode-range div uses both hidden and grid classes toggled by JS syncMode()
- Tailwind rebuild required after templates created (build-css.ps1 ~177ms)
- /api/ruang returned 10 options in QA environment

## Task 22 - E2E Integration Tests (2026-05-16)

- TestClient + monkeypatched orchestrator works perfectly for e2e flow testing
- Key pattern: patch playwright_browser, scraper_login, go_to_pendaftaran_induk, pply_filter, extract_visits on the orchestrator module (not the source modules)
- Use call_idx dict trick to return different batches per successive extract_visits call (simulates multi-date range scraping)
- Poll-based _wait_for_job_status with 50ms sleep is reliable for async background tasks in TestClient
- DB reset pattern: set DATABASE_URL to tmp_path file + clear _engine/_sessionmaker module globals + get_settings.cache_clear()
- Re-scrape semantics confirmed: upsert_recap produces ONE row per date regardless of how many times scraped
- Ruff pre-existing issues in app/main.py (import sort, unused import, line length) - not introduced by tests
