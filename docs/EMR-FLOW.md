# EMR Trenggalek - Flow Documentation

> Discovered: 2026-05-16  
> Target: `https://emrtrenggalek.my.id/daf` — PUSKESMAS BARUHARJO  
> Backend: CodeIgniter 4.2.8

## Login Flow

### URL
`https://emrtrenggalek.my.id/daf` (POST)

### Form Structure
- **Form**: `<form name="form" method="post" action="https://emrtrenggalek.my.id/daf" onsubmit="return validasi_input(this)">`
- **CSRF Token**: `<input type="hidden" name="csrf_token_name" value="...">` — changes per page load
- **Puskesmas**: `<select name="id_cabang">` wrapped in Select2 (class `select2 select2-hidden-accessible`)
  - PUSKESMAS BARUHARJO = value `16`
  - 23 total options (Dinas + 22 puskesmas)
  - **Strategy**: Use native `select_option(value="16")` — Select2 wraps it but native still works via Playwright
- **Username**: `<input name="user" type="text" class="form-control input-sm">`
- **Password**: `<input name="pass" type="password" class="form-control input-sm">`
- **Hidden login flag**: `<input name="login" type="hidden">`
- **Submit**: `<input name="submit" value="Login" type="submit" class="btn btn-success btn-sm">`

### Login Behavior
- POST submits to same URL (`/daf`)
- On success: page reloads with different content (login form disappears, dashboard shown)
- URL stays at `https://emrtrenggalek.my.id/daf` after login
- Page title: "PENDAFTARAN"
- Session maintained via cookies (CI4 session)

### Anti-bot / Rate Limiting
- CSRF token required on every form POST (per-form, per-page-load)
- No CAPTCHA observed
- No rate-limit headers observed
- CodeIgniter debug toolbar present (development mode)

---

## Post-Login Dashboard

### URL
`https://emrtrenggalek.my.id/daf` (same as login, different content when authenticated)

### Navigation Elements
- **Header**: `<h1>PENDAFTARAN- PUSKESMAS BARUHARJO</h1>` (link to `/daf`)
- **PENDAFTARAN INDUK link**: `<a href="https://emrtrenggalek.my.id/daf/px/1/1/0/0">PENDAFTARAN INDUK</a>`
- **Logout**: `<input value="Keluar" name="logout" type="submit" class="btn btn-sm btn-outline-dark">` (in a form POST to `/daf`)

### Key Selector
```css
a[href*='/daf/px/1/1/0/0']
```

---

## Pendaftaran Induk (Patient List)

### URL Pattern
`https://emrtrenggalek.my.id/daf/px/1/{page}/0/0`

- `1` = action code for patient list
- `{page}` = page number (observed as `1`)
- Last two `0/0` = rm_id/visit_id (unused for list view)

### Filter Row

Located in a `<table>` above the main patient table. Labels in first `<tr>`, inputs in second `<tr>`.

| Filter | Input | Type | Notes |
|--------|-------|------|-------|
| No. RM | `input[name='rm'][type='search']` | search | autofocus, autocomplete=off |
| No. RM Lama | `input[name='no_rm_lama']` | text | |
| NIK | `input[name='nik']` | text | |
| Nama | `input[name='nama']` | text | |
| Alamat | `input[name='alamat']` | text | |
| Ruang | `select[name='id_ruangx']` | native select | 24 options (UGD, POLI UMUM, etc.) |
| Dokumen | `select[name='dokumen']` | native select | Semua, Lengkap, Belum Lengkap, Belum diambil |
| Tanggal | `input[name='tanggal'][type='date']` | date | max=today, value=today, format YYYY-MM-DD |

### Search Button
```css
button[title='cari']
```
- Contains `<span class="fa fa-search"></span>`
- Class: `btn btn-sm btn-outline-dark`
- **Behavior**: Appears to be a form submit (GET to same URL with filter params) — NOT AJAX

### Ruang Filter Options (id_ruangx)
| Value | Label |
|-------|-------|
| 0 | (empty/all) |
| 144 | RAWAT INAP |
| 145 | UGD |
| 146 | IMUNISASI |
| 147 | POLI MTBS |
| 148 | POLI KIA |
| 149 | POLI GIGI |
| 150 | POLI UMUM |
| 151 | GUDANG PENYIMPANAN BARANG |
| 153 | PONED |
| 559 | POLI LANSIA |
| 653 | POLI GIZI |
| 654 | POLI REMAJA |
| 655 | POLI SANITASI |
| 656 | POLI KB |
| 657 | POLI AKUPRESSUR |
| 721 | GUDANG OBAT ED/RUSAK |
| 729 | PSC 119 |
| 776 | PROLANIS |
| 870 | POLI CJH |
| 871 | POLI TB |
| 872 | POLI DISABILITAS |
| 873 | CKG |
| 874 | POLI PTM |

### Patient Table

**Selector**: `table.table-sm.table-bordered.table-hover.small`

**Column Structure** (header row):
| # | Column | Width | Notes |
|---|--------|-------|-------|
| 1 | No | 3% | Row number |
| 2 | No. RM | 5% | RM number + "Resume"/"CPPT" buttons |
| 3 | Nama | 8% | Patient name + "Gabung" button |
| 4 | Tgl Lahir | 10% | Birth date + age + BPJS card number |
| 5 | Alamat | auto | Address + screening button |
| 6 | L/P | auto | Gender |
| 7 | Asuransi yg Dimiliki | auto | Insurance info + CEK link |
| 8-9 | Edit Pasien | colspan=2 | "Edit" button + "Kartu" print link |
| 10 | DATA KUNJUNGAN | 40%, colspan=2 | Nested table with visit data |

### Patient Row Structure (per row)
Each `<tr>` in the main table body contains:
- Patient data in columns 1-9
- **Nested visit table** in last column with sub-rows per visit:
  - Ruangan (e.g., UGD) + "Pindah" button
  - Cara Bayar (e.g., UMUM, BPJS) + "Bayar" button + "RM" button
  - Tgl. Masuk (datetime, e.g., "16-05-2026 16:09")
  - Batal (status: "Sdh" = sudah/done)

### Action Buttons (Form POST)
Each action is a `<form method="post">` with CSRF token + `<button>`:

| Action | URL Pattern | Button Text | Purpose |
|--------|-------------|-------------|---------|
| Resume | `/daf/px/15/1/{rm_id}/0` | "Resume" | Open patient resume |
| CPPT | `/rp/res/{visit_id}/0/0` | "CPPT" | Medical record notes |
| Gabung | `/daf/px/31/1/{rm_id}/{visit_id}` | "Gabung" | Merge records |
| Edit | `/daf/px/2/1/{rm_id}/0` | "Edit" | Edit patient data |
| Daftar | `/daf/px/4/1/{rm_id}/0` | "Daftar" | Register new visit |
| Pindah | `/daf/px/4/1/{rm_id}/{visit_id}` | "Pindah" | Transfer room |
| Bayar | `/daf/px/20/1/0/{visit_id}` | "Bayar" | Payment page |
| RM | `/daf/px/30/1/{rm_id}/{visit_id}` | "RM" | Full medical record |

### Pagination
**NOT present.** All patients for the selected date are displayed at once (29 rows observed on 2026-05-16). The URL has a `{page}` parameter but no pagination UI was found.

### Additional Buttons (above patient table)
- **Warga** (new citizen patient): POST to `/daf/px/6/1/0/0`
- **BPJS** (new BPJS patient): POST to `/daf/px/7/1/0/0`
- **Lainnya** (other): POST to `/daf/px/8/1/0/0`
- **CEK BANSOS**: external link to `elinksimpus.my.id`

---

## Detail Behavior (CRITICAL)

### Type: NEW PAGE (Form POST)

Detail is accessed via form POST — **NOT a modal, NOT inline expansion**.

Each action button submits a form with:
1. CSRF token (`csrf_token_name`)
2. Optional hidden fields (e.g., `alamat_asal1` for back-navigation URL)

### For Scraping Tindakan/Biaya:
The most relevant detail pages are:
- **CPPT** (`/rp/res/{visit_id}/0/0`): Contains medical record with tindakan
- **RM** (`/daf/px/30/1/{rm_id}/{visit_id}`): Full medical record view
- **Bayar** (`/daf/px/20/1/0/{visit_id}`): Payment/billing page

### Back Navigation
- The `alamat_asal1` hidden field stores the return URL (e.g., `/daf/px/1/1/0/0`)
- No explicit "Back" button observed — likely uses browser back or the stored return URL

### CSRF Handling for Detail Access
Every form POST requires a fresh CSRF token. Strategy:
1. Parse the patient list page HTML
2. Extract CSRF token from the specific form you want to submit
3. POST with the token to access detail page

---

## Session Management

- **Framework**: CodeIgniter 4.2.8
- **Session**: Cookie-based (CI4 default)
- **CSRF**: Per-form token, regenerated on each page load
- **Timeout**: Not explicitly observed; standard CI4 session timeout applies
- **Login detection**: If `form[name='form']` (login form) is present, session has expired

---

## Scraping Strategy Recommendations

1. **Login**: Use native select + form fill + click submit. Wait for login form to disappear.
2. **Navigate**: Direct GET to `/daf/px/1/1/0/0` after login (session cookie maintained).
3. **Filter by date**: Set `input[name='tanggal']` value, click search button.
4. **Extract patient data**: Parse `table.table-sm.table-bordered.table-hover.small` rows.
5. **Access detail**: Extract CSRF token from the target form, then POST programmatically.
6. **Handle CSRF**: Each page load gives new tokens — must re-extract before each POST.
7. **No pagination needed**: All daily patients shown on one page.

---

## Known Limitations / Gotchas

- CSRF tokens are per-form and per-page-load — cannot reuse across requests
- The `input[name='rm'][type='search']` form has its own action (POST to `/daf/px/1/1/0/0`)
- Patient table has NO `<th>` headers — column order must be inferred from the header row with `<td>` elements
- Nested tables within patient rows make DOM traversal complex
- Date format in the date input is `YYYY-MM-DD` but displayed dates are `DD-MM-YYYY HH:MM`
- The "Sdh" (Sudah) in Batal column indicates visit is finalized
- Debug toolbar (CI4) adds extra tables to the page — filter by class when scraping
