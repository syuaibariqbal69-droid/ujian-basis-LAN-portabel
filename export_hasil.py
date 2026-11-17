#!/usr/bin/env python3
"""Ekspor hasil ujian ke CSV (bisa dibuka di Excel).

Pemakaian:  python export_hasil.py --exam 1 --out hasil.csv
"""
import argparse, csv, os

try:
    import pymysql as driver
    def connect(a): return driver.connect(host=a.host, port=a.port, user=a.user, password=a.password, database=a.db, charset="utf8mb4")
except ImportError:
    import mysql.connector as driver
    def connect(a): return driver.connect(host=a.host, port=a.port, user=a.user, password=a.password, database=a.db)

p = argparse.ArgumentParser()
p.add_argument("--exam", type=int, required=True)
p.add_argument("--out", default="hasil.csv")
p.add_argument("--host", default=os.getenv("DB_HOST", "127.0.0.1"))
p.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "3306")))
p.add_argument("--user", default=os.getenv("DB_USER", "root"))
p.add_argument("--password", default=os.getenv("DB_PASS", ""))
p.add_argument("--db", default=os.getenv("DB_NAME", "ujian_lan"))
a = p.parse_args()

conn = connect(a); cur = conn.cursor()
cur.execute("""SELECT u.username,u.nama,u.kelas,a.mulai,a.selesai,a.benar,a.skor
               FROM attempts a JOIN users u ON u.id=a.user_id
               WHERE a.exam_id=%s ORDER BY u.kelas,u.nama""", (a.exam,))
rows = cur.fetchall()
with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["username", "nama", "kelas", "mulai", "selesai", "benar", "nilai"])
    w.writerows(rows)
conn.close()
print(f"{len(rows)} baris ditulis ke {a.out}")
