# Ujian Online LAN, versi portabel (Python + MySQL/MariaDB)

Seluruh aplikasi, database, dan data ujian berada dalam satu folder. Salin ke flashdisk atau laptop pengawas,
klik start, selesai. Tidak perlu instalasi, tidak perlu internet saat ujian berlangsung.

## Menyiapkan (sekali saja)
Di komputer yang terhubung internet, jalankan `siapkan.bat` (Windows) atau `siapkan.sh` (Linux x86_64).
Skrip ini mengisi folder `libs` (Flask, PyMySQL, Waitress) dan mengunduh **MariaDB portabel** resmi ke `runtime/mariadb`
(lewat `unduh_mysql.py`, ukuran sekitar 100 MB).
Setelah itu folder bisa dibawa ke komputer lain tanpa internet. Python portabel di `runtime/python` bersifat opsional (lihat `runtime/BACA-SAYA.txt`).
Jika unduhan otomatis gagal atau memakai macOS/ARM, ekstrak MariaDB/MySQL ZIP secara manual seperti di `runtime/BACA-SAYA.txt`.

## Menjalankan
- Windows: klik dua kali `start.bat`. Linux/Mac: `./start.sh`.
- Pertama kali, database dibuat otomatis dan admin dibuat (`admin` / `admin123`). Ganti passwordnya di Dashboard.
- Alamat untuk siswa dicetak di jendela, misalnya `http://192.168.1.10:8000`. Izinkan akses jaringan saat Windows Firewall bertanya.
- Menutup jendela atau Ctrl+C menghentikan aplikasi dan menutup database dengan aman.

## Data dan cadangan
- Semua data di `data/` (database `data/mysql`, kunci sesi `data/secret.key`, log `data/mysql.log`).
- Cadangan atau pindah komputer: tutup aplikasi, lalu salin seluruh folder.
- Mulai dari nol: tutup aplikasi lalu hapus folder `data`.

## Tanpa MySQL portabel
Jika folder `runtime` tidak berisi MySQL/MariaDB, aplikasi memakai MySQL yang sudah berjalan
(atur `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS` bila perlu).

## Alat tambahan (format CSV soal: pertanyaan,a,b,c,d,e,kunci)
```
python tools/import_soal.py tools/contoh_soal.csv --exam 1 --port 3307
python tools/export_hasil.py --exam 1 --out hasil.csv --port 3307
```
(`--port 3307` dipakai saat MySQL portabel yang menyala.) Nilai juga bisa diunduh dari menu Hasil.
