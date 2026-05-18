# rekap-in

Aplikasi scraping dan rekapitulasi data EMR Puskesmas berbasis FastAPI + Playwright.

## Quickstart

1. **Clone repo**
   ```bash
   git clone <repo-url>
   cd rekap-in
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt && pip install -r requirements-dev.txt
   ```

3. **Install browser Playwright**
   ```bash
   playwright install chromium
   ```

4. **Isi `.env` dengan kredensial EMR**
   ```bash
   cp .env.example .env
   # Edit .env, isi EMR_USERNAME dan EMR_PASSWORD
   ```

5. **Jalankan aplikasi**
   ```bash
   python -m app
   ```

6. **Buka browser**
   ```
   http://127.0.0.1:8000
   ```

## Struktur Proyek

```
rekap-in/
├── app/          # FastAPI application
├── scraper/      # Playwright scraping logic
├── models/       # SQLAlchemy models
├── config/       # Settings & configuration
├── templates/    # Jinja2 HTML templates
├── static/       # CSS, JS assets
├── tests/        # Test suite
├── exports/      # Output files (xlsx, csv)
├── tools/        # Utility scripts
├── discovery/    # EMR discovery/exploration scripts
└── docs/         # Documentation
```

## Build CSS

### Sekali (production)
```powershell
.\tools\build-css.ps1
```

### Watch mode (development)
```powershell
.\tools\watch-css.ps1
```

CSS dihasilkan di `static/css/output.css` (gitignored - di-build per environment).

## Konfigurasi

Salin `.env.example` ke `.env` dan sesuaikan:

| Key | Default | Keterangan |
|-----|---------|------------|
| `EMR_USERNAME` | _(kosong)_ | Username login EMR |
| `EMR_PASSWORD` | _(kosong)_ | Password login EMR |
| `EMR_BASE_URL` | `https://emrtrenggalek.my.id/daf` | Base URL EMR |
| `EMR_PUSKESMAS` | `PUSKESMAS BARUHARJO` | Nama puskesmas |
| `BROWSER_MODE` | `headless` | `headless` atau `headed` |
| `SCRAPE_TIMEOUT` | `60` | Timeout scraping (detik) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./rekap_in.db` | URL database |
| `APP_HOST` | `127.0.0.1` | Host server |
| `APP_PORT` | `8000` | Port server |

## Troubleshooting

### "Login gagal" / kredensial salah
Pastikan `EMR_USERNAME` dan `EMR_PASSWORD` di `.env` benar. Test di browser dulu di https://emrtrenggalek.my.id/daf.

### "Selector tidak ditemukan"
Struktur halaman EMR mungkin berubah. Jalankan ulang discovery:
```powershell
& .venv\Scripts\python.exe discovery\capture_flow.py
```
Lalu update `config/selectors.yaml` dengan selector baru.

### Browser tidak terbuka
Pastikan Chromium ter-install:
```powershell
& .venv\Scripts\python.exe -m playwright install chromium
```

### CSS tidak ter-update
Build ulang Tailwind:
```powershell
.\tools\build-css.ps1
```

### Database error
Hapus `rekap_in.db` dan jalankan ulang aplikasi (akan dibuat ulang otomatis).

## Pengembangan

### Run tests
```powershell
& .venv\Scripts\python.exe -m pytest tests\ -v
```

### Tambah ruang baru
Edit `config\ruang.py` dan tambah nama ruang baru ke `RUANG_LIST`.
Edit `scraper\ruang_map.py` jika EMR menambah ruang baru (mapping nama -> id_ruangx).

### Mode debug (browser visible)
Edit `.env`:
```
BROWSER_MODE=headed
```
