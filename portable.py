#!/usr/bin/env python3
"""Peluncur portabel: menyalakan MySQL/MariaDB portabel + aplikasi ujian dari satu folder.

Semua data tersimpan di folder data/ sehingga seluruh folder bisa dibawa lewat flashdisk.
Urutan: 1) pakai MySQL/MariaDB di runtime/ bila ada, 2) bila tidak ada, pakai MySQL yang sudah berjalan.
"""
import glob, os, socket, subprocess, sys, time, webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "libs"))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data")
MYDATA = os.path.join(DATA, "mysql")
os.makedirs(DATA, exist_ok=True)
os.environ.setdefault("APP_DATA", DATA)
WIN = os.name == "nt"
EXE = ".exe" if WIN else ""
DB_PORT = 3307  # port khusus agar tidak bentrok dengan MySQL lain di komputer


def keluar(pesan):
    print("\n" + pesan)
    if WIN:
        input("\nTekan Enter untuk menutup...")
    sys.exit(1)


def port_terbuka(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def cari_server():
    """Cari mysqld/mariadbd portabel di folder runtime/. Mengembalikan (basedir, binary) atau None."""
    for pola in ("mariadb*", "mysql*", "MariaDB*", "MySQL*"):
        for d in glob.glob(os.path.join(BASE, "runtime", pola)):
            for nama in ("mariadbd", "mysqld"):
                b = os.path.join(d, "bin", nama + EXE)
                if os.path.exists(b):
                    return d, b
    return None


def siapkan_datadir(basedir, server):
    if os.path.isdir(os.path.join(MYDATA, "mysql")):
        return
    print("Menyiapkan database untuk pertama kali (sekitar 30 detik)...")
    os.makedirs(MYDATA, exist_ok=True)
    kandidat = [os.path.join(basedir, "bin", "mariadb-install-db" + EXE),
                os.path.join(basedir, "bin", "mysql_install_db" + EXE),
                os.path.join(basedir, "scripts", "mariadb-install-db"),
                os.path.join(basedir, "scripts", "mysql_install_db")]
    for k in kandidat:
        if os.path.exists(k):
            cmd = [k, f"--datadir={MYDATA}"] + ([] if WIN else [f"--basedir={basedir}", "--auth-root-authentication-method=normal"])
            if subprocess.run(cmd, cwd=basedir, capture_output=True).returncode == 0:
                return
    # MySQL resmi
    r = subprocess.run([server, "--initialize-insecure", f"--datadir={MYDATA}", f"--basedir={basedir}"], capture_output=True)
    if r.returncode != 0:
        keluar("Gagal menyiapkan database:\n" + r.stderr.decode(errors="replace")[-600:])


def nyalakan_db(basedir, server):
    siapkan_datadir(basedir, server)
    cmd = [server, f"--datadir={MYDATA}", f"--basedir={basedir}", f"--port={DB_PORT}",
           "--bind-address=127.0.0.1", f"--pid-file={os.path.join(DATA, 'mysql.pid')}"]
    if WIN:
        cmd.append("--console")
    else:
        cmd.append(f"--socket={os.path.join(DATA, 'mysql.sock')}")
    log = open(os.path.join(DATA, "mysql.log"), "ab")
    flags = 0x08000000 if WIN else 0  # CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, stdout=log, stderr=log, cwd=basedir, creationflags=flags)
    for _ in range(90):
        if proc.poll() is not None:
            keluar("MySQL/MariaDB berhenti sendiri. Lihat data/mysql.log untuk rinciannya.")
        if port_terbuka("127.0.0.1", DB_PORT):
            return proc
        time.sleep(1)
    proc.terminate()
    keluar("MySQL/MariaDB tidak siap dalam 90 detik. Lihat data/mysql.log.")


def matikan_db(proc):
    if not proc:
        return
    print("Menutup database...")
    try:
        import pymysql
        c = pymysql.connect(host="127.0.0.1", port=DB_PORT, user="root", password="", connect_timeout=3)
        with c.cursor() as cur:
            cur.execute("SHUTDOWN")
    except Exception:
        proc.terminate()
    try:
        proc.wait(40)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    try:
        import flask, pymysql, waitress  # noqa: F401
    except ImportError:
        keluar("Library belum lengkap. Jalankan siapkan.bat (Windows) atau siapkan.sh (Linux/Mac) dulu, "
               "di komputer yang terhubung internet.")

    proc = None
    ketemu = cari_server()
    if ketemu:
        os.environ["DB_HOST"], os.environ["DB_PORT"] = "127.0.0.1", str(DB_PORT)
        if not port_terbuka("127.0.0.1", DB_PORT):
            proc = nyalakan_db(*ketemu)
    else:
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = int(os.getenv("DB_PORT", "3306"))
        if not port_terbuka(host, port):
            keluar("MySQL/MariaDB portabel tidak ditemukan di folder runtime/ dan tidak ada MySQL yang berjalan.\n"
                   "Baca runtime/BACA-SAYA.txt.")

    try:
        import pymysql
        import app as web
        try:
            pymysql.connect(**{**web.DB, "cursorclass": pymysql.cursors.Cursor}).close()
        except pymysql.err.OperationalError as e:
            if e.args and e.args[0] == 1049:  # database belum ada
                web.init_db()
            else:
                keluar(f"Tidak bisa terhubung ke database: {e}")
        web.ensure_admin()
        url = f"http://localhost:{web.PORT}/admin"
        print(f"\nSiswa membuka:  http://{web.lan_ip()}:{web.PORT}\nPengawas:       {url}")
        print("Tutup jendela ini (atau tekan Ctrl+C) untuk menghentikan ujian.\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        from waitress import serve
        serve(web.app, host="0.0.0.0", port=web.PORT, threads=16)
    except KeyboardInterrupt:
        pass
    finally:
        matikan_db(proc)


if __name__ == "__main__":
    main()
