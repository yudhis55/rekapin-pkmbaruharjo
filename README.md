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

### Catatan Penting Produksi
- Gunakan `APP_HOST=0.0.0.0` agar aplikasi bisa diakses dari perangkat lain dalam jaringan lokal.
- Pastikan mode browser diatur ke `headless` di `.env`.
- Instal dependensi sistem untuk Playwright di server:
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
