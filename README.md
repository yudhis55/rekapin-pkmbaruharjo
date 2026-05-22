# Rekap-In

Aplikasi scraping dan rekapitulasi data EMR (Electronic Medical Record) Puskesmas berbasis FastAPI dan Playwright. Aplikasi ini dirancang untuk mengotomatisasi pengambilan data kunjungan pasien dan menghasilkan laporan rekapitulasi harian dalam format Excel.

## Fitur Utama

- **Scraping Data Otomatis**: Mengambil data kunjungan pasien langsung dari sistem EMR.
- **Filter Fleksibel**: Filter data berdasarkan rentang tanggal, poli/ruangan, dan metode pembayaran (Umum/BPJS).
- **Monitoring Real-time**: Pantau proses scraping dan lihat hasil kunjungan secara langsung di tabel aplikasi.
- **Ekspor Excel (.xlsx)**: Menghasilkan file laporan rekapitulasi harian yang siap cetak sesuai format standar.
- **Riwayat Rekap**: Akses kembali data rekapitulasi dari hari-hari sebelumnya dengan mudah.

## Quickstart (Development)

Ikuti langkah-langkah berikut untuk menjalankan aplikasi di lingkungan pengembangan (Windows PowerShell):

1. **Clone Repositori**
   ```powershell
   git clone <repo-url>
   cd rekap-in
   ```

2. **Persiapkan Virtual Environment**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Instal Dependensi**
   ```powershell
   pip install -r requirements.txt
   # Opsional: Instal tools pengembangan
   pip install -r requirements-dev.txt
   ```

4. **Instal Playwright Browser**
   ```powershell
   & .venv\Scripts\python.exe -m playwright install chromium
   ```

5. **Konfigurasi Environment**
   Salin file contoh `.env` dan isi kredensial EMR Anda:
   ```powershell
   copy .env.example .env
   ```

6. **Build CSS (Tailwind)**
   ```powershell
   .\tools\build-css.ps1
   ```

7. **Jalankan Aplikasi**
   ```powershell
   & .venv\Scripts\python.exe -m app
   ```
   Buka [http://127.0.0.1:8000](http://127.0.0.1:8000) di browser Anda.

## Konfigurasi (.env)

| Kunci | Default | Deskripsi |
|-------|---------|-----------|
| `EMR_USERNAME` | - | Username untuk login ke sistem EMR |
| `EMR_PASSWORD` | - | Password untuk login ke sistem EMR |
| `EMR_BASE_URL` | `https://emrtrenggalek.my.id/daf` | URL utama sistem EMR |
| `EMR_PUSKESMAS` | `PUSKESMAS BARUHARJO` | Nama instansi Puskesmas |
| `BROWSER_MODE` | `headless` | Mode browser (`headless` untuk tanpa jendela, `headed` untuk melihat proses) |
| `SCRAPE_TIMEOUT` | `60` | Batas waktu tunggu proses scraping (detik) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./rekap_in.db` | Koneksi database SQLite |
| `APP_HOST` | `127.0.0.1` | Host server aplikasi |
| `APP_PORT` | `8000` | Port server aplikasi |

## Struktur Proyek

- `app/`: Logika inti aplikasi FastAPI.
  - `excel/`: Modul pembuat laporan Excel.
  - `routes/`: Definisi endpoint API dan web.
  - `db/`: Konfigurasi database dan repositori.
- `scraper/`: Logika otomasi Playwright untuk EMR.
- `models/`: Definisi model data SQLAlchemy.
- `templates/`: Template HTML menggunakan Jinja2.
- `static/`: Aset statis (CSS hasil build, JavaScript, gambar).
- `tools/`: Skrip utilitas (build CSS, dll).
- `exports/`: Direktori penyimpanan sementara file hasil ekspor.

## Build CSS

Aplikasi ini menggunakan Tailwind CSS. Jika Anda melakukan perubahan pada tampilan:

- **Build Sekali (Production)**:
  ```powershell
  .\tools\build-css.ps1
  ```
- **Mode Pantau (Development)**:
  ```powershell
  .\tools\watch-css.ps1
  ```

## Cara Penggunaan

1. **Tentukan Parameter**: Pilih tanggal kunjungan dan cara bayar di halaman utama.
2. **Mulai Scraping**: Klik tombol **Mulai Scraping**. Sistem akan membuka browser di latar belakang dan mengumpulkan data.
3. **Pantau Proses**: Tunggu hingga progress bar mencapai 100%. Data akan muncul di tabel secara bertahap.
4. **Ekspor Laporan**: Setelah selesai, klik **Ekspor Excel** untuk mengunduh file `.xlsx`.
5. **Cek Riwayat**: Gunakan tabel Riwayat Rekap untuk melihat atau mengunduh ulang rekapitulasi dari tanggal lain.

## Deploy ke Produksi

### Opsi A: Windows (NSSM sebagai Windows Service)
Gunakan [NSSM](https://nssm.cc/) untuk menjalankan aplikasi secara otomatis saat server menyala.

```powershell
# Jalankan di terminal dengan hak akses Administrator
nssm install rekap-in "C:\path\to\rekap-in\.venv\Scripts\python.exe" "-m app"
nssm set rekap-in AppDirectory "C:\path\to\rekap-in"
nssm set rekap-in AppEnvironmentExtra "APP_HOST=0.0.0.0" "APP_PORT=8000"
nssm start rekap-in
```

### Opsi B: Linux (systemd)
Buat file service di `/etc/systemd/system/rekap-in.service`:

```ini
[Unit]
Description=Rekap-In EMR Scraper
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/rekap-in
ExecStart=/opt/rekap-in/.venv/bin/python -m app
Restart=on-failure
RestartSec=5
Environment=APP_HOST=127.0.0.1
Environment=APP_PORT=8000

[Install]
WantedBy=multi-user.target
```

Aktivasi service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rekap-in
sudo systemctl start rekap-in
```

### Konfigurasi Nginx Reverse Proxy (Linux)
```nginx
server {
    listen 80;
    server_name rekap.puskesmas.local;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Dukungan SSE (Server-Sent Events)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

### Opsi C: cPanel Shared Hosting (Setup Python App)

Rekap-In **bisa** berjalan di cPanel shared hosting selama hosting Anda menyediakan Python 3.11 dan system libraries Chromium sudah tersedia di server. Verifikasi dulu dengan menjalankan test di bawah sebelum melanjutkan.

#### Prasyarat — Test di Terminal cPanel

Buka **Terminal** di cPanel (Advanced → Terminal), lalu jalankan:

```bash
# Test 1: Pastikan Python 3.11 tersedia
/opt/alt/python311/bin/python3 -V
# Harus output: Python 3.11.x

# Test 2: Buat venv test dan install Playwright
/opt/alt/python311/bin/python3 -m venv ~/test-pw
source ~/test-pw/bin/activate
pip install playwright
python -m playwright install chromium

# Test 3: Launch Chromium — ini penentu utama
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK'); b.close(); p.stop()"

# Bersihkan test
deactivate
rm -rf ~/test-pw
```

Jika Test 3 mencetak `OK` → lanjutkan. Jika error → hosting Anda tidak support, gunakan Opsi B (VPS).

---

#### Langkah 1: Upload Kode ke Server

Di terminal cPanel, clone repo ke home directory:

```bash
cd ~
git clone <repo-url> rekap-in
cd rekap-in
```

Atau upload via **File Manager** cPanel, lalu ekstrak ke folder `rekap-in`.

---

#### Langkah 2: Setup Python App di cPanel

1. Buka cPanel → **Software** → **Setup Python App**
2. Klik **CREATE APPLICATION**
3. Isi form:
   - **Python version**: `3.11.x` (pilih yang tersedia)
   - **Application root**: `rekap-in`
   - **Application URL**: pilih domain/subdomain Anda (misal `rekap.namadomain.com` atau `namadomain.com/rekap`)
   - **Application startup file**: `passenger_wsgi.py`
   - **Application Entry point**: `application`
4. Klik **CREATE**

cPanel akan membuat virtualenv otomatis di `~/virtualenv/rekap-in/`.

---

#### Langkah 3: Buat File `passenger_wsgi.py`

File ini diperlukan agar Passenger (web server cPanel) bisa menjalankan FastAPI (ASGI) sebagai WSGI.

Di terminal cPanel:

```bash
cd ~/rekap-in
cat > passenger_wsgi.py << 'EOF'
import sys
import os

# Pastikan path aplikasi ada di sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Import ASGI-to-WSGI bridge
from a2wsgi import ASGIMiddleware
from app.main import create_app

# Buat FastAPI app dan wrap dengan ASGIMiddleware
fastapi_app = create_app()
application = ASGIMiddleware(fastapi_app)
EOF
```

---

#### Langkah 4: Install Dependencies

Di terminal cPanel, aktifkan virtualenv yang dibuat cPanel lalu install semua dependencies:

```bash
# Aktifkan virtualenv cPanel (sesuaikan username dan versi)
source ~/virtualenv/rekap-in/3.11/bin/activate && cd ~/rekap-in

# Install dependencies aplikasi
pip install -r requirements.txt

# Install a2wsgi (ASGI-to-WSGI bridge, wajib untuk cPanel)
pip install a2wsgi

# Install Playwright browser
python -m playwright install chromium
```

---

#### Langkah 5: Konfigurasi `.env`

```bash
cd ~/rekap-in
cp .env.example .env
```

Edit file `.env` via File Manager cPanel atau `nano`:

```bash
nano .env
```

Isi minimal yang wajib diubah:

```env
EMR_USERNAME=username_emr_anda
EMR_PASSWORD=password_emr_anda
APP_HOST=127.0.0.1
APP_PORT=8000
BROWSER_MODE=headless
```

> **Penting**: `APP_HOST` tetap `127.0.0.1` — Passenger yang handle routing dari luar, bukan uvicorn langsung.

---

#### Langkah 6: Build CSS

```bash
# Pastikan Node.js tersedia (cek dulu)
node -v || nodejs -v

# Jika ada, build CSS
cd ~/rekap-in
npx tailwindcss -i static/css/input.css -o static/css/output.css --minify
```

Jika Node.js tidak tersedia di terminal, upload file `static/css/output.css` yang sudah di-build dari komputer lokal via File Manager.

---

#### Langkah 7: Restart Aplikasi

Kembali ke cPanel → **Setup Python App** → klik **RESTART** pada aplikasi Anda.

Atau via terminal:

```bash
touch ~/rekap-in/tmp/restart.txt
```

---

#### Langkah 8: Verifikasi

Buka URL aplikasi di browser (sesuai Application URL yang diset di langkah 2). Jika muncul halaman Rekap-In → berhasil.

Jika error, cek log Passenger:

```bash
tail -50 ~/logs/rekap-in.log
# atau
tail -50 ~/rekap-in/logs/passenger.log
```

---

#### Troubleshooting cPanel

| Error | Penyebab | Solusi |
|-------|----------|--------|
| `ModuleNotFoundError: a2wsgi` | a2wsgi belum install | `pip install a2wsgi` di virtualenv cPanel |
| `Error: Failed to launch browser` | System libs Chromium tidak ada | Hosting tidak support, gunakan VPS |
| `Internal Server Error` tanpa detail | passenger_wsgi.py salah | Cek log, pastikan `application` terdefinisi |
| Halaman kosong / CSS tidak muncul | output.css belum ada | Upload `static/css/output.css` dari lokal |
| `No module named app` | Path salah | Pastikan `sys.path.insert` di passenger_wsgi.py benar |

---

### Catatan Penting Produksi
- Gunakan `APP_HOST=0.0.0.0` agar aplikasi bisa diakses dari perangkat lain dalam jaringan lokal (khusus VPS/dedicated, bukan cPanel).
- Pastikan mode browser diatur ke `headless` di `.env`.
- Untuk VPS Linux, install system dependencies Playwright:
  ```bash
  .venv/bin/python -m playwright install chromium --with-deps
  ```
- Database SQLite disimpan di `rekap_in.db`, pastikan untuk melakukan backup berkala.

## Pengembangan

### Menjalankan Test
```powershell
& .venv\Scripts\python.exe -m pytest tests\ -v
```

### Linting
```powershell
& .venv\Scripts\python.exe -m ruff check .
```

### Tambah Ruang/Poli Baru
Edit `config\ruang.py` dan tambah nama ruang baru ke `RUANG_LIST`.
Edit `scraper\ruang_map.py` jika EMR menambah ruang baru (mapping nama → id_ruangx).

### Mode Debug (Browser Terlihat)
Edit `.env`:
```
BROWSER_MODE=headed
```

## Troubleshooting

- **Ekspor Excel gagal**: Pastikan data sudah berhasil di-scrape. Cek log server untuk detail error.
- **Tampilan berantakan / CSS tidak muncul**: Jalankan `.\tools\build-css.ps1` untuk rebuild CSS.
- **Gagal login EMR**: Periksa username dan password di `.env`. Test login manual di browser ke URL EMR.
- **"Selector tidak ditemukan"**: Struktur halaman EMR mungkin berubah. Jalankan ulang discovery:
  ```powershell
  & .venv\Scripts\python.exe discovery\capture_flow.py
  ```
  Lalu update `config\selectors.yaml` dengan selector baru.
- **Browser tidak terbuka**: Pastikan Chromium ter-install:
  ```powershell
  & .venv\Scripts\python.exe -m playwright install chromium
  ```
- **Database error**: Hapus `rekap_in.db` dan jalankan ulang aplikasi (akan dibuat ulang otomatis).
