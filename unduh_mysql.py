#!/usr/bin/env python3
"""Mengunduh MariaDB portabel (arsip ZIP/tar.gz resmi) ke runtime/mariadb.

Jalankan sekali di komputer yang terhubung internet:
    python unduh_mysql.py                 # versi bawaan
    python unduh_mysql.py --versi 10.11.9 # versi lain (cek archive.mariadb.org)
Setelah selesai, seluruh folder aplikasi bisa dibawa ke komputer lain tanpa internet.
"""
import argparse, os, platform, shutil, sys, tarfile, tempfile, urllib.request, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
RT = os.path.join(BASE, "runtime")
TARGET = os.path.join(RT, "mariadb")
EXE = ".exe" if os.name == "nt" else ""
VERSI = "10.11.9"  # seri LTS


def alamat(v):
    mesin = platform.machine().lower()
    if os.name == "nt":
        return f"https://archive.mariadb.org/mariadb-{v}/winx64-packages/mariadb-{v}-winx64.zip"
    if sys.platform.startswith("linux") and mesin in ("x86_64", "amd64"):
        return f"https://archive.mariadb.org/mariadb-{v}/bintar-linux-systemd-x86_64/mariadb-{v}-linux-systemd-x86_64.tar.gz"
    return None


def manual(url=None):
    print("\nUnduh manual: ambil versi ZIP/tar.gz dari https://mariadb.org/download lalu ekstrak sehingga ada")
    print(f"  {os.path.join('runtime', 'mariadb', 'bin', 'mariadbd' + EXE)}")
    if url:
        print(f"Alamat yang dicoba: {url}")
    sys.exit(1)


def progres(blok, ukuran, total):
    if total > 0:
        persen = min(100, blok * ukuran * 100 // total)
        print(f"\rMengunduh... {persen}%  ({total // 1048576} MB)", end="", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versi", default=VERSI)
    a = ap.parse_args()

    if os.path.exists(os.path.join(TARGET, "bin", "mariadbd" + EXE)):
        print("MariaDB portabel sudah ada di runtime/mariadb. Tidak ada yang perlu diunduh.")
        return
    url = alamat(a.versi)
    if not url:
        print("Sistem ini (mis. macOS atau ARM) tidak punya arsip portabel otomatis.")
        manual()

    os.makedirs(RT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=RT)
    arsip = os.path.join(tmp, "mariadb.arc")
    try:
        print(f"Sumber: {url}")
        urllib.request.urlretrieve(url, arsip, progres)
        print("\nMengekstrak...")
        if url.endswith(".zip"):
            zipfile.ZipFile(arsip).extractall(tmp)
        else:
            with tarfile.open(arsip) as t:
                t.extractall(tmp)
        os.remove(arsip)
        isi = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        if len(isi) != 1:
            raise RuntimeError("Susunan arsip tidak dikenali")
        sumber = os.path.join(tmp, isi[0])
        if not os.path.exists(os.path.join(sumber, "bin", "mariadbd" + EXE)):
            raise RuntimeError("mariadbd tidak ditemukan di dalam arsip")
        for sampah in ("mysql-test", "sql-bench", "debug"):  # hemat ruang flashdisk
            shutil.rmtree(os.path.join(sumber, sampah), ignore_errors=True)
        if os.path.exists(TARGET):
            shutil.rmtree(TARGET)
        shutil.move(sumber, TARGET)
        print("Selesai. MariaDB portabel terpasang di runtime/mariadb.")
    except Exception as e:
        print(f"\nGagal: {e}")
        manual(url)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
