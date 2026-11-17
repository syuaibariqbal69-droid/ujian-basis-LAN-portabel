#!/usr/bin/env python3
"""Ujian Online LAN: Python (Flask) + MySQL, jalan offline.

Pemakaian:
    python app.py --init-db     # sekali saja: membuat database dan tabel
    python app.py               # jalankan server di jaringan LAN (port 8000)
"""
import csv, io, os, secrets, socket, sys
from functools import wraps

import pymysql
import pymysql.cursors
from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.getenv("PORT", "8000"))
DB = dict(host=os.getenv("DB_HOST", "127.0.0.1"), user=os.getenv("DB_USER", "root"),
          password=os.getenv("DB_PASS", ""), port=int(os.getenv("DB_PORT", "3306")), database=os.getenv("DB_NAME", "ujian_lan"),
          charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)

app = Flask(__name__)
DATA = os.getenv("APP_DATA", BASE)
os.makedirs(DATA, exist_ok=True)
key_file = os.path.join(DATA, "secret.key")
if not os.path.exists(key_file):
    with open(key_file, "w") as f:
        f.write(secrets.token_hex(32))
app.secret_key = open(key_file).read().strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


# ---------- Database ----------
def db():
    if "db" not in g:
        g.db = pymysql.connect(**DB)
    return g.db

@app.teardown_appcontext
def close_db(_):
    c = g.pop("db", None)
    if c:
        c.close()

def q(sql, args=(), one=False):
    with db().cursor() as c:
        c.execute(sql, args)
        return c.fetchone() if one else c.fetchall()

def ex(sql, args=()):
    with db().cursor() as c:
        return c.execute(sql, args)

def finish_attempt(att_id):
    a = q("SELECT exam_id FROM attempts WHERE id=%s AND selesai IS NULL", (att_id,), True)
    if not a:
        return
    r = q("""SELECT COUNT(*) t, COALESCE(SUM(an.jawaban = q.kunci),0) b
             FROM questions q LEFT JOIN answers an ON an.question_id=q.id AND an.attempt_id=%s
             WHERE q.exam_id=%s""", (att_id, a["exam_id"]), True)
    skor = round(float(r["b"]) / r["t"] * 100, 2) if r["t"] else 0
    ex("UPDATE attempts SET selesai=NOW(), benar=%s, skor=%s WHERE id=%s AND selesai IS NULL",
       (int(r["b"]), skor, att_id))


# ---------- Keamanan ----------
def csrf():
    if "t" not in session:
        session["t"] = secrets.token_hex(16)
    return session["t"]

app.jinja_env.globals["csrf"] = csrf

@app.before_request
def cek_csrf():
    if request.method == "POST":
        if not secrets.compare_digest(session.get("t", ""), request.form.get("t", "")):
            abort(400, "Sesi tidak valid. Muat ulang halaman.")

def role_required(role, api=False):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **k):
            u = session.get("u")
            if not u or u["role"] != role:
                if api:
                    return jsonify(ok=False), 403
                return redirect(url_for("index"))
            return fn(*a, **k)
        return wrap
    return deco


# ---------- Login ----------
@app.route("/", methods=["GET", "POST"])
def index():
    err = ""
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE username=%s", (request.form.get("username", "").strip(),), True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["u"] = {"id": u["id"], "nama": u["nama"], "role": u["role"]}
        else:
            err = "Username atau password salah."
    u = session.get("u")
    if u:
        return redirect(url_for("admin_dash" if u["role"] == "admin" else "ujian"))
    return render_template("login.html", err=err)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- Siswa ----------
@app.route("/ujian")
@role_required("siswa")
def ujian():
    rows = q("""SELECT e.*, a.id aid, a.selesai, a.skor,
                (SELECT COUNT(*) FROM questions WHERE exam_id=e.id) jml
                FROM exams e LEFT JOIN attempts a ON a.exam_id=e.id AND a.user_id=%s
                WHERE e.aktif=1 OR a.id IS NOT NULL ORDER BY e.id DESC""", (session["u"]["id"],))
    return render_template("ujian.html", rows=rows)

@app.route("/soal/<int:eid>")
@role_required("siswa")
def soal(eid):
    uid = session["u"]["id"]
    exam = q("SELECT * FROM exams WHERE id=%s AND aktif=1", (eid,), True)
    if not exam:
        return redirect(url_for("ujian"))
    ex("INSERT IGNORE INTO attempts(exam_id,user_id,mulai) VALUES(%s,%s,NOW())", (eid, uid))
    att = q("""SELECT *, TIMESTAMPDIFF(SECOND, NOW(), DATE_ADD(mulai, INTERVAL %s MINUTE)) sisa
               FROM attempts WHERE exam_id=%s AND user_id=%s""", (exam["durasi_menit"], eid, uid), True)
    if att["selesai"]:
        return redirect(url_for("ujian"))
    if att["sisa"] <= 0:
        finish_attempt(att["id"])
        return redirect(url_for("ujian"))
    order = f"RAND({int(att['id'])})" if exam["acak_soal"] else "id"
    daftar = q(f"SELECT id, pertanyaan, a, b, c, d, e FROM questions WHERE exam_id=%s ORDER BY {order}", (eid,))
    jawab = {r["question_id"]: r["jawaban"] for r in
             q("SELECT question_id, jawaban FROM answers WHERE attempt_id=%s", (att["id"],))}
    return render_template("soal.html", exam=exam, soal=daftar, jawab=jawab, sisa=int(att["sisa"]), eid=eid)

@app.post("/api/<aksi>")
@role_required("siswa", api=True)
def api(aksi):
    uid = session["u"]["id"]
    eid = request.form.get("exam", type=int, default=0)
    att = q("""SELECT a.id, a.selesai,
               TIMESTAMPDIFF(SECOND, NOW(), DATE_ADD(a.mulai, INTERVAL e.durasi_menit MINUTE)) sisa
               FROM attempts a JOIN exams e ON e.id=a.exam_id WHERE a.exam_id=%s AND a.user_id=%s""",
            (eid, uid), True)
    if not att or att["selesai"]:
        return jsonify(ok=False, expired=True)
    if aksi == "finish":
        finish_attempt(att["id"])
        return jsonify(ok=True)
    if att["sisa"] < -5:
        finish_attempt(att["id"])
        return jsonify(ok=False, expired=True)
    if aksi == "save":
        j = request.form.get("j", "").lower()
        qid = request.form.get("q", type=int, default=0)
        if j not in ("a", "b", "c", "d", "e") or not q("SELECT 1 FROM questions WHERE id=%s AND exam_id=%s", (qid, eid), True):
            return jsonify(ok=False)
        ex("""INSERT INTO answers(attempt_id,question_id,jawaban) VALUES(%s,%s,%s)
              ON DUPLICATE KEY UPDATE jawaban=VALUES(jawaban)""", (att["id"], qid, j))
        return jsonify(ok=True)
    return jsonify(ok=False)


# ---------- Admin ----------
def halaman(p, **kw):
    return render_template("admin.html", p=p, **kw)

@app.route("/admin")
@role_required("admin")
def admin_dash():
    st = q("""SELECT (SELECT COUNT(*) FROM users WHERE role='siswa') siswa,
              (SELECT COUNT(*) FROM exams WHERE aktif=1) aktif,
              (SELECT COUNT(*) FROM attempts WHERE selesai IS NULL) jalan,
              (SELECT COUNT(*) FROM attempts WHERE selesai IS NOT NULL) selesai""", one=True)
    live = q("""SELECT u.nama, u.kelas, e.judul,
                TIMESTAMPDIFF(SECOND, NOW(), DATE_ADD(a.mulai, INTERVAL e.durasi_menit MINUTE)) sisa,
                (SELECT COUNT(*) FROM answers WHERE attempt_id=a.id) terjawab,
                (SELECT COUNT(*) FROM questions WHERE exam_id=e.id) total
                FROM attempts a JOIN users u ON u.id=a.user_id JOIN exams e ON e.id=a.exam_id
                WHERE a.selesai IS NULL ORDER BY a.mulai""")
    for l in live:
        l["pct"] = round(l["terjawab"] / l["total"] * 100) if l["total"] else 0
        s = max(0, int(l["sisa"]))
        l["sisa_txt"] = "Waktu habis" if l["sisa"] <= 0 else f"{s // 60:02d}:{s % 60:02d}"
    return halaman("dash", st=st, live=live)

@app.route("/admin/ujian")
@role_required("admin")
def admin_ujian():
    rows = q("SELECT e.*, (SELECT COUNT(*) FROM questions WHERE exam_id=e.id) jml FROM exams e ORDER BY id DESC")
    return halaman("ujian", rows=rows)

@app.route("/admin/soal/<int:eid>")
@role_required("admin")
def admin_soal(eid):
    exam = q("SELECT * FROM exams WHERE id=%s", (eid,), True) or abort(404)
    return halaman("soal", exam=exam, rows=q("SELECT * FROM questions WHERE exam_id=%s ORDER BY id", (eid,)))

@app.route("/admin/siswa")
@role_required("admin")
def admin_siswa():
    return halaman("siswa", rows=q("SELECT * FROM users WHERE role='siswa' ORDER BY kelas, nama"))

@app.route("/admin/hasil")
@role_required("admin")
def admin_hasil():
    exams = q("SELECT id, judul FROM exams ORDER BY id DESC")
    eid = request.args.get("e", type=int, default=exams[0]["id"] if exams else 0)
    rows = q("""SELECT a.id, u.nama, u.kelas, a.mulai, a.selesai, a.benar, a.skor
                FROM attempts a JOIN users u ON u.id=a.user_id WHERE a.exam_id=%s
                ORDER BY u.kelas, u.nama""", (eid,)) if eid else []
    return halaman("hasil", exams=exams, eid=eid, rows=rows)

@app.route("/admin/csv/<int:eid>")
@role_required("admin")
def admin_csv(eid):
    rows = q("""SELECT u.username, u.nama, u.kelas, a.mulai, a.selesai, a.benar, a.skor
                FROM attempts a JOIN users u ON u.id=a.user_id WHERE a.exam_id=%s
                ORDER BY u.kelas, u.nama""", (eid,))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["username", "nama", "kelas", "mulai", "selesai", "benar", "nilai"])
    for r in rows:
        w.writerow(r.values())
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="hasil-ujian-{eid}.csv"'})

@app.post("/admin/act")
@role_required("admin")
def admin_act():
    f, a = request.form, request.form.get("a", "")
    if a == "exam":
        ex("INSERT INTO exams(judul,durasi_menit,acak_soal) VALUES(%s,%s,%s)",
           (f["judul"].strip(), max(1, f.get("durasi", type=int, default=60)), 1 if f.get("acak") else 0))
        flash("Ujian dibuat. Tambahkan soal, lalu buka ujian.")
    elif a == "toggle":
        ex("UPDATE exams SET aktif=1-aktif WHERE id=%s", (f.get("id", type=int),))
    elif a == "delexam":
        ex("DELETE FROM exams WHERE id=%s", (f.get("id", type=int),))
        flash("Ujian dihapus.")
    elif a == "soal":
        k = f.get("kunci", "").lower()
        if k in ("a", "b", "c", "d", "e"):
            ex("INSERT INTO questions(exam_id,pertanyaan,a,b,c,d,e,kunci) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
               (f.get("exam", type=int), f["pertanyaan"].strip(), f["a"].strip(), f["b"].strip(),
                f["c"].strip(), f["d"].strip(), f["e"].strip(), k))
            flash("Soal ditambahkan.")
    elif a == "delsoal":
        ex("DELETE FROM questions WHERE id=%s", (f.get("id", type=int),))
    elif a == "siswa":  # tiap baris: username,nama,kelas,password
        n = 0
        for row in csv.reader(io.StringIO(f.get("data", "").strip())):
            c = [x.strip() for x in row]
            if len(c) < 4 or not c[0]:
                continue
            ex("""INSERT INTO users(username,password_hash,nama,kelas,role) VALUES(%s,%s,%s,%s,'siswa')
                  ON DUPLICATE KEY UPDATE nama=VALUES(nama), kelas=VALUES(kelas), password_hash=VALUES(password_hash)""",
               (c[0], generate_password_hash(c[3]), c[1], c[2]))
            n += 1
        flash(f"{n} akun siswa disimpan.")
    elif a == "delsiswa":
        ex("DELETE FROM users WHERE id=%s AND role='siswa'", (f.get("id", type=int),))
    elif a == "reset":
        ex("DELETE FROM attempts WHERE id=%s", (f.get("id", type=int),))
        flash("Percobaan ujian direset. Siswa bisa mengulang.")
    elif a == "password":
        if len(f.get("baru", "")) >= 6:
            ex("UPDATE users SET password_hash=%s WHERE id=%s",
               (generate_password_hash(f["baru"]), session["u"]["id"]))
            flash("Password admin diganti.")
        else:
            flash("Password minimal 6 karakter.")
    return redirect(request.referrer or url_for("admin_dash"))


# ---------- Setup dan menjalankan ----------
def init_db():
    cfg = {k: v for k, v in DB.items() if k != "database"}
    conn = pymysql.connect(**{**cfg, "cursorclass": pymysql.cursors.Cursor})
    with open(os.path.join(BASE, "database.sql"), encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as c:
        for st in sql.split(";"):
            if st.strip():
                c.execute(st)
    conn.close()
    print("Database dan tabel siap.")

def ensure_schema():
    """Migrasi otomatis untuk database lama: tambahkan kolom pilihan E bila belum ada."""
    if not q("""SELECT 1 FROM information_schema.columns
                WHERE table_schema=DATABASE() AND table_name='questions' AND column_name='e'""", one=True):
        ex("ALTER TABLE questions ADD COLUMN e VARCHAR(500) NOT NULL DEFAULT '' AFTER d")
        print("Database diperbarui: kolom pilihan E ditambahkan (soal lama tetap 4 pilihan).")

def ensure_admin():
    with app.app_context():
        ensure_schema()
        if not q("SELECT 1 FROM users WHERE role='admin' LIMIT 1", one=True):
            ex("INSERT INTO users(username,password_hash,nama,role) VALUES('admin',%s,'Administrator','admin')",
               (generate_password_hash("admin123"),))
            print("Akun admin dibuat: admin / admin123 (segera ganti di menu Siswa).")

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # tidak mengirim data, hanya memilih antarmuka LAN
        return s.getsockname()[0]
    except OSError:
        return "IP-SERVER"
    finally:
        s.close()

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
        sys.exit()
    try:
        ensure_admin()
    except pymysql.err.Error as e:
        sys.exit(f"Tidak bisa terhubung ke MySQL: {e}\nJalankan MySQL, lalu 'python app.py --init-db' bila database belum dibuat.")
    print(f"\nSiswa membuka:  http://{lan_ip()}:{PORT}\nPengawas:       http://localhost:{PORT}/admin\n")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT, threads=16)
    except ImportError:
        app.run(host="0.0.0.0", port=PORT, threaded=True)
