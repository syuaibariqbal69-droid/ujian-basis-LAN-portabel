#!/usr/bin/env python3
"""Impor soal dari CSV ke MySQL.

Format CSV (baris pertama header): pertanyaan,a,b,c,d,e,kunci
Pemakaian:  python import_soal.py soal.csv --exam 1
Butuh:      pip install pymysql   (atau mysql-connector-python)
"""
import argparse, csv, os, sys

try:
    import pymysql as driver
    def connect(a): return driver.connect(host=a.host, port=a.port, user=a.user, password=a.password, database=a.db, charset="utf8mb4")
except ImportError:
    import mysql.connector as driver
    def connect(a): return driver.connect(host=a.host, port=a.port, user=a.user, password=a.password, database=a.db)

p = argparse.ArgumentParser()
p.add_argument("csv_file")
p.add_argument("--exam", type=int, required=True, help="ID ujian tujuan")
p.add_argument("--host", default=os.getenv("DB_HOST", "127.0.0.1"))
p.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "3306")))
p.add_argument("--user", default=os.getenv("DB_USER", "root"))
p.add_argument("--password", default=os.getenv("DB_PASS", ""))
p.add_argument("--db", default=os.getenv("DB_NAME", "ujian_lan"))
a = p.parse_args()

conn = connect(a); cur = conn.cursor()
ok = skip = 0
with open(a.csv_file, newline="", encoding="utf-8-sig") as f:
    for no, r in enumerate(csv.DictReader(f), start=2):
        kunci = (r.get("kunci") or "").strip().lower()
        if kunci not in ("a", "b", "c", "d", "e") or not (r.get("pertanyaan") or "").strip() or not (r.get("e") or "").strip():
            print(f"Baris {no} dilewati: pertanyaan atau pilihan E kosong, atau kunci bukan a/b/c/d/e"); skip += 1; continue
        cur.execute("INSERT INTO questions(exam_id,pertanyaan,a,b,c,d,e,kunci) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (a.exam, r["pertanyaan"].strip(), r["a"].strip(), r["b"].strip(), r["c"].strip(), r["d"].strip(), r["e"].strip(), kunci))
        ok += 1
conn.commit(); conn.close()
print(f"Selesai: {ok} soal diimpor, {skip} dilewati.")
