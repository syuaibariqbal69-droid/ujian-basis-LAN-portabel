#!/bin/sh
cd "$(dirname "$0")"
echo "[1/2] Mengunduh library Python ke folder libs (butuh internet, cukup sekali)..."
python3 -m pip install -r requirements.txt --target libs --upgrade
echo "[2/2] Memeriksa MariaDB portabel..."
[ -x runtime/mariadb/bin/mariadbd ] || python3 unduh_mysql.py
echo "Selesai. Jalankan ./start.sh"
