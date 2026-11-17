@echo off
cd /d "%~dp0"
echo [1/2] Mengunduh library Python ke folder libs (butuh internet, cukup sekali)...
python -m pip install -r requirements.txt --target libs --upgrade
echo.
echo [2/2] Memeriksa MariaDB portabel...
if not exist runtime\mariadb\bin\mariadbd.exe python unduh_mysql.py
echo.
echo Selesai. Sekarang jalankan start.bat
pause
