"""Storage — SQLite untuk Sistem Jamur Tiram."""
from __future__ import annotations
import hashlib, sqlite3, time, uuid
from pathlib import Path


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    nama        TEXT NOT NULL,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'operator',
    aktif       INTEGER NOT NULL DEFAULT 1,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id              TEXT PRIMARY KEY,
    kode            TEXT NOT NULL UNIQUE,
    nama            TEXT NOT NULL DEFAULT '',
    tanggal_mulai   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pengadukan',
    catatan         TEXT DEFAULT '',
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pengadukan (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id            TEXT NOT NULL REFERENCES batches(id),
    tanggal             TEXT NOT NULL,
    serbuk_gergaji_kg   REAL DEFAULT 0,
    bekatul_kg          REAL DEFAULT 0,
    kapur_kg            REAL DEFAULT 0,
    air_liter           REAL DEFAULT 0,
    catatan             TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pengisian_baglog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL REFERENCES batches(id),
    tanggal         TEXT NOT NULL,
    jumlah_baglog   INTEGER DEFAULT 0,
    operator        TEXT DEFAULT '',
    catatan         TEXT DEFAULT '',
    plastik_pcs     INTEGER DEFAULT 0,
    cincin_pcs      INTEGER DEFAULT 0,
    tutup_pcs       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sterilisasi (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id            TEXT NOT NULL REFERENCES batches(id),
    tanggal             TEXT NOT NULL,
    jumlah_baglog       INTEGER DEFAULT 0,
    jam_mulai           TEXT DEFAULT '',
    jam_selesai         TEXT DEFAULT '',
    durasi_jam          REAL DEFAULT 0,
    suhu                REAL DEFAULT 0,
    biaya_bahan_bakar   REAL DEFAULT 0,
    kayu_bakar_kg       REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inokulasi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL REFERENCES batches(id),
    tanggal         TEXT NOT NULL,
    jenis_bibit     TEXT DEFAULT '',
    kode_bibit      TEXT DEFAULT '',
    jumlah_baglog   INTEGER DEFAULT 0,
    catatan         TEXT DEFAULT '',
    bibit_botol     REAL DEFAULT 0,
    alkohol_liter   REAL DEFAULT 0,
    karet_pcs       INTEGER DEFAULT 0,
    koran_lembar    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inkubasi (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id                TEXT NOT NULL REFERENCES batches(id),
    tanggal_mulai           TEXT NOT NULL,
    tanggal_selesai         TEXT DEFAULT '',
    jumlah_baglog           INTEGER DEFAULT 0,
    baglog_gagal            INTEGER DEFAULT 0,
    persentase_keberhasilan REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS panen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL REFERENCES batches(id),
    tanggal         TEXT NOT NULL,
    berat_kg        REAL NOT NULL DEFAULT 0,
    kualitas        TEXT DEFAULT 'A',
    harga_estimasi  REAL DEFAULT 0,
    catatan         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS penjualan_baglog (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id            TEXT NOT NULL REFERENCES batches(id),
    tanggal             TEXT NOT NULL,
    nama_pembeli        TEXT DEFAULT '',
    nomor_hp            TEXT DEFAULT '',
    jumlah_baglog       INTEGER DEFAULT 0,
    harga_per_baglog    REAL DEFAULT 0,
    total               REAL DEFAULT 0,
    status_bayar        TEXT DEFAULT 'lunas',
    catatan             TEXT DEFAULT '',
    created_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pelanggan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama        TEXT NOT NULL,
    nomor_hp    TEXT DEFAULT '',
    alamat      TEXT DEFAULT '',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS penjualan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal         TEXT NOT NULL,
    pelanggan_id    INTEGER DEFAULT NULL,
    nama_pembeli    TEXT DEFAULT '',
    nomor_hp        TEXT DEFAULT '',
    tipe_jual       TEXT DEFAULT 'timbang',
    jenis_paket     TEXT DEFAULT '',
    jumlah_bungkus  INTEGER DEFAULT 0,
    berat_kg        REAL NOT NULL DEFAULT 0,
    harga_per_kg    REAL NOT NULL DEFAULT 0,
    total           REAL NOT NULL DEFAULT 0,
    status_bayar    TEXT DEFAULT 'lunas',
    catatan         TEXT DEFAULT '',
    batch_id        TEXT DEFAULT NULL,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pembelian_bahan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal     TEXT NOT NULL,
    nama_bahan  TEXT NOT NULL,
    jumlah      REAL DEFAULT 0,
    satuan      TEXT DEFAULT '',
    harga_satuan REAL DEFAULT 0,
    total       REAL DEFAULT 0,
    catatan     TEXT DEFAULT '',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS biaya_operasional (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal     TEXT NOT NULL,
    kategori    TEXT DEFAULT '',
    keterangan  TEXT DEFAULT '',
    nominal     REAL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bahan_baku (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama        TEXT NOT NULL UNIQUE,
    satuan      TEXT DEFAULT 'kg',
    stok        REAL DEFAULT 0,
    harga_satuan REAL DEFAULT 0,
    stok_min    REAL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS transaksi_bahan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bahan_id    INTEGER NOT NULL REFERENCES bahan_baku(id),
    tanggal     TEXT NOT NULL,
    tipe        TEXT NOT NULL,
    jumlah      REAL NOT NULL DEFAULT 0,
    harga_satuan REAL DEFAULT 0,
    total       REAL DEFAULT 0,
    keterangan  TEXT DEFAULT '',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pembayaran_piutang (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_penjual TEXT NOT NULL,
    tanggal      TEXT NOT NULL,
    jumlah       REAL NOT NULL DEFAULT 0,
    catatan      TEXT DEFAULT '',
    created_at   INTEGER NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        con = self._conn()
        con.executescript(SCHEMA)
        con.commit()
        self._migrate(con)
        self._seed_admin(con)
        self._seed_bahan(con)
        con.close()

    def _migrate(self, con):
        migrations = [
            ("penjualan",    "tipe_jual",       "TEXT DEFAULT 'timbang'"),
            ("penjualan",    "jenis_paket",      "TEXT DEFAULT ''"),
            ("penjualan",    "jumlah_bungkus",   "INTEGER DEFAULT 0"),
            ("penjualan",    "batch_id",         "TEXT DEFAULT NULL"),
            ("transaksi_bahan", "batch_id",      "TEXT DEFAULT NULL"),
            ("sterilisasi",  "jumlah_baglog",    "INTEGER DEFAULT 0"),
        ]
        for tbl, col, defn in migrations:
            try:
                con.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
                con.commit()
            except Exception:
                pass

    def _conn(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _seed_admin(self, con):
        if not con.execute("SELECT id FROM users").fetchone():
            con.execute(
                "INSERT INTO users (id,nama,username,password,role,aktif,created_at) VALUES (?,?,?,?,?,1,?)",
                (uuid.uuid4().hex[:8], "Administrator", "admin", _hash("admin123"), "admin", int(time.time()))
            )
            con.commit()

    DEFAULT_BAHAN = [
        ("Serbuk Gergaji",  "kg",     0, 50),
        ("Dedak/Bekatul",   "kg",     0, 20),
        ("Kapur",           "kg",     0, 5),
        ("Plastik Baglog",  "pcs",    0, 500),
        ("Cincin",          "pcs",    0, 500),
        ("Tutup Cincin",    "pcs",    0, 500),
        ("Kayu Bakar",      "kg",     0, 50),
        ("Bibit Jamur",     "botol",  0, 10),
        ("Alkohol",         "liter",  0, 1),
        ("Karet Gelang",    "pcs",    0, 100),
        ("Kertas Koran",    "lembar", 0, 50),
    ]

    def _seed_bahan(self, con):
        for nama, satuan, harga, stok_min in self.DEFAULT_BAHAN:
            existing = con.execute("SELECT id FROM bahan_baku WHERE nama=?", (nama,)).fetchone()
            if not existing:
                con.execute(
                    "INSERT INTO bahan_baku (nama,satuan,harga_satuan,stok_min,stok,created_at) VALUES (?,?,?,?,0,?)",
                    (nama, satuan, harga, stok_min, int(time.time()))
                )
        con.commit()

    def _deduct_bahan(self, con, nama: str, jumlah: float, tanggal: str, keterangan: str, batch_id: str = ""):
        if jumlah <= 0:
            return
        row = con.execute("SELECT id FROM bahan_baku WHERE LOWER(nama)=LOWER(?)", (nama,)).fetchone()
        if not row:
            return
        bahan_id = row[0]
        con.execute(
            "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,batch_id,created_at) VALUES (?,?,'keluar',?,0,0,?,?,?)",
            (bahan_id, tanggal, jumlah, keterangan, batch_id or None, int(time.time()))
        )
        con.execute("UPDATE bahan_baku SET stok=stok-? WHERE id=?", (jumlah, bahan_id))

    # ── Users ─────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict | None:
        con = self._conn()
        row = con.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND aktif=1",
            (username, _hash(password))
        ).fetchone()
        con.close()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        con = self._conn()
        rows = con.execute("SELECT * FROM users ORDER BY nama").fetchall()
        con.close()
        return [dict(r) for r in rows]

    def create_user(self, nama: str, username: str, password: str, role: str) -> str:
        uid = uuid.uuid4().hex[:8]
        con = self._conn()
        con.execute(
            "INSERT INTO users (id,nama,username,password,role,aktif,created_at) VALUES (?,?,?,?,?,1,?)",
            (uid, nama, username, _hash(password), role, int(time.time()))
        )
        con.commit()
        con.close()
        return uid

    def update_user(self, uid: str, nama: str, role: str, password: str = ""):
        con = self._conn()
        if password:
            con.execute("UPDATE users SET nama=?,role=?,password=? WHERE id=?", (nama, role, _hash(password), uid))
        else:
            con.execute("UPDATE users SET nama=?,role=? WHERE id=?", (nama, role, uid))
        con.commit()
        con.close()

    def delete_user(self, uid: str):
        con = self._conn()
        con.execute("DELETE FROM users WHERE id=?", (uid,))
        con.commit()
        con.close()

    # ── Batches ───────────────────────────────────────────────────────────────

    def list_batches(self, status: str = "") -> list[dict]:
        con = self._conn()
        if status:
            rows = con.execute("SELECT * FROM batches WHERE status=? ORDER BY tanggal_mulai DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM batches ORDER BY tanggal_mulai DESC").fetchall()
        con.close()
        return [dict(r) for r in rows]

    def get_batch(self, bid: str) -> dict | None:
        con = self._conn()
        row = con.execute("SELECT * FROM batches WHERE id=?", (bid,)).fetchone()
        con.close()
        return dict(row) if row else None

    def create_batch(self, kode: str, nama: str, tanggal_mulai: str) -> str:
        bid = uuid.uuid4().hex[:8]
        con = self._conn()
        con.execute(
            "INSERT INTO batches (id,kode,nama,tanggal_mulai,status,created_at) VALUES (?,?,?,?,?,?)",
            (bid, kode, nama, tanggal_mulai, "pengadukan", int(time.time()))
        )
        con.commit()
        con.close()
        return bid

    def advance_batch(self, bid: str, to_status: str):
        con = self._conn()
        con.execute("UPDATE batches SET status=? WHERE id=?", (to_status, bid))
        con.commit()
        con.close()

    def update_batch(self, bid: str, kode: str, nama: str, tanggal_mulai: str, status: str, catatan: str):
        con = self._conn()
        con.execute(
            "UPDATE batches SET kode=?,nama=?,tanggal_mulai=?,status=?,catatan=? WHERE id=?",
            (kode, nama, tanggal_mulai, status, catatan, bid)
        )
        con.commit()
        con.close()

    def delete_batch(self, bid: str):
        con = self._conn()
        try:
            # Batalkan semua transaksi stok yang terkait batch ini
            rows = con.execute(
                "SELECT bahan_id, tipe, jumlah FROM transaksi_bahan WHERE batch_id=?", (bid,)
            ).fetchall()
            for r in rows:
                if r["tipe"] == "keluar":
                    con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (r["jumlah"], r["bahan_id"]))
                else:
                    con.execute("UPDATE bahan_baku SET stok=MAX(0,stok-?) WHERE id=?", (r["jumlah"], r["bahan_id"]))
            con.execute("DELETE FROM transaksi_bahan WHERE batch_id=?", (bid,))
            # Hapus semua data anak
            for tbl in ("pengadukan", "pengisian_baglog", "sterilisasi",
                        "inokulasi", "inkubasi", "panen", "penjualan_baglog"):
                con.execute(f"DELETE FROM {tbl} WHERE batch_id=?", (bid,))
            con.execute("UPDATE penjualan SET batch_id=NULL WHERE batch_id=?", (bid,))
            con.execute("DELETE FROM batches WHERE id=?", (bid,))
            con.commit()
        finally:
            con.close()

    # ── Pengadukan ────────────────────────────────────────────────────────────

    def save_pengadukan(self, batch_id, tanggal, serbuk, bekatul, kapur, air, catatan):
        batch = self.get_batch(batch_id)
        ket = f"Pengadukan batch {batch['kode'] if batch else batch_id}"
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO pengadukan (batch_id,tanggal,serbuk_gergaji_kg,bekatul_kg,kapur_kg,air_liter,catatan) VALUES (?,?,?,?,?,?,?)",
                (batch_id, tanggal, serbuk, bekatul, kapur, air, catatan)
            )
            self._deduct_bahan(con, "Serbuk Gergaji", serbuk,  tanggal, ket, batch_id)
            self._deduct_bahan(con, "Dedak/Bekatul",  bekatul, tanggal, ket, batch_id)
            self._deduct_bahan(con, "Kapur",          kapur,   tanggal, ket, batch_id)
            con.execute("UPDATE batches SET status='pengisian' WHERE id=? AND status='pengadukan'", (batch_id,))
            con.commit()
        finally:
            con.close()

    def get_pengadukan(self, batch_id) -> dict | None:
        con = self._conn()
        row = con.execute("SELECT * FROM pengadukan WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        con.close()
        return dict(row) if row else None

    # ── Pengisian Baglog (multi-sesi) ─────────────────────────────────────────

    def list_pengisian(self, batch_id) -> list[dict]:
        con = self._conn()
        rows = con.execute("SELECT * FROM pengisian_baglog WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_pengisian(self, batch_id, tanggal, jumlah_baglog, operator, catatan="",
                       plastik=0, cincin=0, tutup=0):
        batch = self.get_batch(batch_id)
        ket = f"Logging batch {batch['kode'] if batch else batch_id}"
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO pengisian_baglog (batch_id,tanggal,jumlah_baglog,operator,catatan,plastik_pcs,cincin_pcs,tutup_pcs) VALUES (?,?,?,?,?,?,?,?)",
                (batch_id, tanggal, jumlah_baglog, operator, catatan, plastik, cincin, tutup)
            )
            self._deduct_bahan(con, "Plastik Baglog", plastik, tanggal, ket, batch_id)
            self._deduct_bahan(con, "Cincin",         cincin,  tanggal, ket, batch_id)
            self._deduct_bahan(con, "Tutup Cincin",   tutup,   tanggal, ket, batch_id)
            con.commit()
        finally:
            con.close()

    def delete_pengisian(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM pengisian_baglog WHERE id=?", (pid,))
        con.commit()
        con.close()

    # ── Sterilisasi ───────────────────────────────────────────────────────────

    # ── Sterilisasi (multi-sesi) ──────────────────────────────────────────────

    def list_sterilisasi(self, batch_id) -> list[dict]:
        con = self._conn()
        rows = con.execute("SELECT * FROM sterilisasi WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_sterilisasi(self, batch_id, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya, kayu_bakar_kg=0):
        batch = self.get_batch(batch_id)
        ket = f"Sterilisasi batch {batch['kode'] if batch else batch_id}"
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO sterilisasi (batch_id,tanggal,jumlah_baglog,jam_mulai,jam_selesai,durasi_jam,suhu,biaya_bahan_bakar,kayu_bakar_kg) VALUES (?,?,?,?,?,?,?,?,?)",
                (batch_id, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya, kayu_bakar_kg)
            )
            self._deduct_bahan(con, "Kayu Bakar", kayu_bakar_kg, tanggal, ket, batch_id)
            con.commit()
        finally:
            con.close()

    def delete_sterilisasi(self, sid: int):
        con = self._conn()
        try:
            row = con.execute("SELECT batch_id, tanggal, kayu_bakar_kg FROM sterilisasi WHERE id=?", (sid,)).fetchone()
            if row and row["kayu_bakar_kg"]:
                bahan = con.execute("SELECT id FROM bahan_baku WHERE LOWER(nama)='kayu bakar'").fetchone()
                if bahan:
                    con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (row["kayu_bakar_kg"], bahan["id"]))
                    con.execute("DELETE FROM transaksi_bahan WHERE batch_id=? AND tipe='keluar' AND tanggal=? AND bahan_id=?",
                                (row["batch_id"], row["tanggal"], bahan["id"]))
            con.execute("DELETE FROM sterilisasi WHERE id=?", (sid,))
            con.commit()
        finally:
            con.close()

    # ── Inokulasi / Pembibitan (multi-sesi) ──────────────────────────────────

    def list_inokulasi(self, batch_id) -> list[dict]:
        con = self._conn()
        rows = con.execute("SELECT * FROM inokulasi WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_inokulasi(self, batch_id, tanggal, jenis_bibit, kode_bibit, jumlah_baglog, catatan="",
                       bibit_botol=0, alkohol_liter=0, karet_pcs=0, koran_lembar=0):
        batch = self.get_batch(batch_id)
        ket = f"Pembibitan batch {batch['kode'] if batch else batch_id}"
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO inokulasi (batch_id,tanggal,jenis_bibit,kode_bibit,jumlah_baglog,catatan,bibit_botol,alkohol_liter,karet_pcs,koran_lembar) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (batch_id, tanggal, jenis_bibit, kode_bibit, jumlah_baglog, catatan, bibit_botol, alkohol_liter, karet_pcs, koran_lembar)
            )
            self._deduct_bahan(con, "Bibit Jamur",  bibit_botol,   tanggal, ket, batch_id)
            self._deduct_bahan(con, "Alkohol",      alkohol_liter, tanggal, ket, batch_id)
            self._deduct_bahan(con, "Karet Gelang", karet_pcs,     tanggal, ket, batch_id)
            self._deduct_bahan(con, "Kertas Koran", koran_lembar,  tanggal, ket, batch_id)
            con.commit()
        finally:
            con.close()

    def delete_inokulasi(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM inokulasi WHERE id=?", (pid,))
        con.commit()
        con.close()

    # ── Inkubasi ──────────────────────────────────────────────────────────────

    def save_inkubasi(self, batch_id, tanggal_mulai, tanggal_selesai, jumlah, gagal):
        persen = round(((jumlah - gagal) / jumlah * 100) if jumlah > 0 else 0, 1)
        con = self._conn()
        con.execute(
            "INSERT INTO inkubasi (batch_id,tanggal_mulai,tanggal_selesai,jumlah_baglog,baglog_gagal,persentase_keberhasilan) VALUES (?,?,?,?,?,?)",
            (batch_id, tanggal_mulai, tanggal_selesai, jumlah, gagal, persen)
        )
        con.execute("UPDATE batches SET status='panen' WHERE id=? AND status='inkubasi'", (batch_id,))
        con.commit()
        con.close()

    def get_inkubasi(self, batch_id) -> dict | None:
        con = self._conn()
        row = con.execute("SELECT * FROM inkubasi WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        con.close()
        return dict(row) if row else None

    # ── Panen ─────────────────────────────────────────────────────────────────

    def list_panen(self, batch_id: str = "") -> list[dict]:
        con = self._conn()
        if batch_id:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM panen p JOIN batches b ON b.id=p.batch_id WHERE p.batch_id=? ORDER BY p.tanggal DESC",
                (batch_id,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM panen p JOIN batches b ON b.id=p.batch_id ORDER BY p.tanggal DESC"
            ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_panen(self, batch_id, tanggal, berat_kg, kualitas, harga_estimasi, catatan):
        con = self._conn()
        con.execute(
            "INSERT INTO panen (batch_id,tanggal,berat_kg,kualitas,harga_estimasi,catatan) VALUES (?,?,?,?,?,?)",
            (batch_id, tanggal, berat_kg, kualitas, harga_estimasi, catatan)
        )
        con.commit()
        con.close()

    def delete_panen(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM panen WHERE id=?", (pid,))
        con.commit()
        con.close()

    # ── Penjualan Baglog ──────────────────────────────────────────────────────

    def list_penjualan_baglog(self, batch_id: str = "", bulan: str = "") -> list[dict]:
        con = self._conn()
        if batch_id:
            rows = con.execute(
                "SELECT pb.*, b.kode as batch_kode FROM penjualan_baglog pb JOIN batches b ON b.id=pb.batch_id WHERE pb.batch_id=? ORDER BY pb.tanggal DESC",
                (batch_id,)
            ).fetchall()
        elif bulan:
            rows = con.execute(
                "SELECT pb.*, b.kode as batch_kode FROM penjualan_baglog pb JOIN batches b ON b.id=pb.batch_id WHERE pb.tanggal LIKE ? ORDER BY pb.tanggal DESC",
                (f"{bulan}%",)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT pb.*, b.kode as batch_kode FROM penjualan_baglog pb JOIN batches b ON b.id=pb.batch_id ORDER BY pb.tanggal DESC"
            ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_penjualan_baglog(self, batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, status_bayar, catatan):
        total = jumlah_baglog * harga_per_baglog
        con = self._conn()
        con.execute(
            "INSERT INTO penjualan_baglog (batch_id,tanggal,nama_pembeli,nomor_hp,jumlah_baglog,harga_per_baglog,total,status_bayar,catatan,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, total, status_bayar, catatan, int(time.time()))
        )
        con.commit()
        con.close()

    def delete_penjualan_baglog(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM penjualan_baglog WHERE id=?", (pid,))
        con.commit()
        con.close()

    # ── Penjualan Jamur ───────────────────────────────────────────────────────

    def list_penjualan(self, bulan: str = "", batch_id: str = "") -> list[dict]:
        con = self._conn()
        if batch_id:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM penjualan p LEFT JOIN batches b ON b.id=p.batch_id WHERE p.batch_id=? ORDER BY p.tanggal DESC",
                (batch_id,)
            ).fetchall()
        elif bulan:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM penjualan p LEFT JOIN batches b ON b.id=p.batch_id WHERE p.tanggal LIKE ? ORDER BY p.tanggal DESC",
                (f"{bulan}%",)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM penjualan p LEFT JOIN batches b ON b.id=p.batch_id ORDER BY p.tanggal DESC"
            ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_penjualan(self, tanggal, nama_pembeli, nomor_hp, berat_kg, harga_per_kg, status_bayar, catatan,
                       batch_id=None, tipe_jual="timbang", jenis_paket="", jumlah_bungkus=0):
        total = round(berat_kg * harga_per_kg if tipe_jual == "timbang" else jumlah_bungkus * harga_per_kg, 2)
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO penjualan (tanggal,nama_pembeli,nomor_hp,tipe_jual,jenis_paket,jumlah_bungkus,berat_kg,harga_per_kg,total,status_bayar,catatan,batch_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tanggal, nama_pembeli, nomor_hp, tipe_jual, jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg, total, status_bayar, catatan, batch_id or None, int(time.time()))
            )
            con.commit()
        finally:
            con.close()

    def delete_penjualan(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM penjualan WHERE id=?", (pid,))
        con.commit()
        con.close()

    def update_penjualan(self, pid: int, tanggal, nama_pembeli, nomor_hp, tipe_jual,
                         jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg,
                         status_bayar, catatan, batch_id=None):
        total = round(berat_kg * harga_per_kg if tipe_jual == "timbang" else jumlah_bungkus * harga_per_kg, 2)
        con = self._conn()
        try:
            con.execute(
                """UPDATE penjualan SET tanggal=?,nama_pembeli=?,nomor_hp=?,tipe_jual=?,
                   jenis_paket=?,jumlah_bungkus=?,berat_kg=?,harga_per_kg=?,total=?,
                   status_bayar=?,catatan=?,batch_id=? WHERE id=?""",
                (tanggal, nama_pembeli, nomor_hp, tipe_jual, jenis_paket, jumlah_bungkus,
                 berat_kg, harga_per_kg, total, status_bayar, catatan, batch_id or None, pid)
            )
            con.commit()
        finally:
            con.close()

    # ── Piutang ───────────────────────────────────────────────────────────────

    def list_piutang(self) -> list[dict]:
        """Daftar penjual yang masih punya hutang."""
        con = self._conn()
        try:
            rows = con.execute("""
                SELECT nama_pembeli,
                       COUNT(*) as jumlah_transaksi,
                       SUM(total) as total_hutang
                FROM penjualan
                WHERE nama_pembeli IS NOT NULL AND nama_pembeli != ''
                  AND status_bayar = 'hutang'
                GROUP BY nama_pembeli
                ORDER BY total_hutang DESC
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_penjualan_hutang(self, nama: str) -> list[dict]:
        """Transaksi hutang untuk satu penjual, urut terlama dulu."""
        con = self._conn()
        try:
            rows = con.execute(
                "SELECT p.*, b.kode as batch_kode FROM penjualan p LEFT JOIN batches b ON b.id=p.batch_id WHERE p.nama_pembeli=? AND p.status_bayar='hutang' ORDER BY p.tanggal ASC, p.id ASC",
                (nama,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_pembayaran_piutang(self, nama: str = "") -> list[dict]:
        con = self._conn()
        try:
            if nama:
                rows = con.execute(
                    "SELECT * FROM pembayaran_piutang WHERE nama_penjual=? ORDER BY tanggal DESC, created_at DESC",
                    (nama,)
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM pembayaran_piutang ORDER BY tanggal DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def save_pembayaran_piutang(self, nama_penjual: str, tanggal: str, jumlah: float, catatan: str):
        """Catat pembayaran dan otomatis lunasi transaksi terlama dulu."""
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO pembayaran_piutang (nama_penjual,tanggal,jumlah,catatan,created_at) VALUES (?,?,?,?,?)",
                (nama_penjual, tanggal, jumlah, catatan, int(time.time()))
            )
            sisa = jumlah
            rows = con.execute(
                "SELECT id, total FROM penjualan WHERE nama_pembeli=? AND status_bayar='hutang' ORDER BY tanggal ASC, id ASC",
                (nama_penjual,)
            ).fetchall()
            for row in rows:
                if sisa <= 0:
                    break
                if sisa >= row["total"]:
                    con.execute("UPDATE penjualan SET status_bayar='lunas' WHERE id=?", (row["id"],))
                    sisa -= row["total"]
            con.commit()
        finally:
            con.close()

    def delete_pembayaran_piutang(self, pid: int):
        con = self._conn()
        try:
            con.execute("DELETE FROM pembayaran_piutang WHERE id=?", (pid,))
            con.commit()
        finally:
            con.close()

    # ── Pembelian Bahan ───────────────────────────────────────────────────────

    def list_pembelian(self, bulan: str = "") -> list[dict]:
        con = self._conn()
        if bulan:
            rows = con.execute("SELECT * FROM pembelian_bahan WHERE tanggal LIKE ? ORDER BY tanggal DESC", (f"{bulan}%",)).fetchall()
        else:
            rows = con.execute("SELECT * FROM pembelian_bahan ORDER BY tanggal DESC").fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_pembelian(self, tanggal, nama_bahan, jumlah, satuan, harga_satuan, catatan):
        total = jumlah * harga_satuan
        con = self._conn()
        try:
            con.execute(
                "INSERT INTO pembelian_bahan (tanggal,nama_bahan,jumlah,satuan,harga_satuan,total,catatan,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (tanggal, nama_bahan, jumlah, satuan, harga_satuan, total, catatan, int(time.time()))
            )
            row = con.execute("SELECT id FROM bahan_baku WHERE LOWER(nama)=LOWER(?)", (nama_bahan,)).fetchone()
            if row:
                bahan_id = row["id"]
                con.execute(
                    "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,created_at) VALUES (?,?,'masuk',?,?,?,?,?)",
                    (bahan_id, tanggal, jumlah, harga_satuan, total, f"Pembelian: {catatan or nama_bahan}", int(time.time()))
                )
                if harga_satuan > 0:
                    con.execute("UPDATE bahan_baku SET stok=stok+?, harga_satuan=? WHERE id=?", (jumlah, harga_satuan, bahan_id))
                else:
                    con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (jumlah, bahan_id))
            con.commit()
        finally:
            con.close()

    def delete_pembelian(self, pid: int):
        con = self._conn()
        con.execute("DELETE FROM pembelian_bahan WHERE id=?", (pid,))
        con.commit()
        con.close()

    # ── Biaya Operasional ─────────────────────────────────────────────────────

    def list_operasional(self, bulan: str = "") -> list[dict]:
        con = self._conn()
        if bulan:
            rows = con.execute("SELECT * FROM biaya_operasional WHERE tanggal LIKE ? ORDER BY tanggal DESC", (f"{bulan}%",)).fetchall()
        else:
            rows = con.execute("SELECT * FROM biaya_operasional ORDER BY tanggal DESC").fetchall()
        con.close()
        return [dict(r) for r in rows]

    def save_operasional(self, tanggal, kategori, keterangan, nominal):
        con = self._conn()
        con.execute(
            "INSERT INTO biaya_operasional (tanggal,kategori,keterangan,nominal,created_at) VALUES (?,?,?,?,?)",
            (tanggal, kategori, keterangan, nominal, int(time.time()))
        )
        con.commit()
        con.close()

    def delete_operasional(self, oid: int):
        con = self._conn()
        con.execute("DELETE FROM biaya_operasional WHERE id=?", (oid,))
        con.commit()
        con.close()

    # ── Bahan Baku & Stok ─────────────────────────────────────────────────────

    def list_bahan(self) -> list[dict]:
        con = self._conn()
        rows = con.execute("SELECT * FROM bahan_baku ORDER BY nama").fetchall()
        con.close()
        return [dict(r) for r in rows]

    def get_bahan(self, bid: int) -> dict | None:
        con = self._conn()
        row = con.execute("SELECT * FROM bahan_baku WHERE id=?", (bid,)).fetchone()
        con.close()
        return dict(row) if row else None

    def save_bahan(self, nama, satuan, harga_satuan, stok_min) -> int:
        con = self._conn()
        cur = con.execute(
            "INSERT INTO bahan_baku (nama,satuan,harga_satuan,stok_min,stok,created_at) VALUES (?,?,?,?,0,?)",
            (nama, satuan, harga_satuan, stok_min, int(time.time()))
        )
        bid = cur.lastrowid
        con.commit()
        con.close()
        return bid

    def update_bahan(self, bid: int, nama: str, satuan: str, harga_satuan: float, stok_min: float):
        con = self._conn()
        con.execute(
            "UPDATE bahan_baku SET nama=?,satuan=?,harga_satuan=?,stok_min=? WHERE id=?",
            (nama, satuan, harga_satuan, stok_min, bid)
        )
        con.commit()
        con.close()

    def delete_bahan(self, bid: int):
        con = self._conn()
        con.execute("DELETE FROM bahan_baku WHERE id=?", (bid,))
        con.commit()
        con.close()

    def stok_masuk(self, bahan_id, tanggal, jumlah, harga_satuan, keterangan):
        total = jumlah * harga_satuan
        con = self._conn()
        con.execute(
            "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,created_at) VALUES (?,?,'masuk',?,?,?,?,?)",
            (bahan_id, tanggal, jumlah, harga_satuan, total, keterangan, int(time.time()))
        )
        if harga_satuan > 0:
            con.execute("UPDATE bahan_baku SET stok=stok+?, harga_satuan=? WHERE id=?", (jumlah, harga_satuan, bahan_id))
        else:
            con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (jumlah, bahan_id))
        con.commit()
        con.close()

    def stok_keluar(self, bahan_id, tanggal, jumlah, keterangan):
        con = self._conn()
        con.execute(
            "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,created_at) VALUES (?,?,'keluar',?,0,0,?,?)",
            (bahan_id, tanggal, jumlah, keterangan, int(time.time()))
        )
        con.execute("UPDATE bahan_baku SET stok=MAX(0, stok-?) WHERE id=?", (jumlah, bahan_id))
        con.commit()
        con.close()

    def delete_transaksi_bahan(self, tid: int):
        con = self._conn()
        # Kembalikan stok sebelum hapus
        row = con.execute("SELECT bahan_id, tipe, jumlah FROM transaksi_bahan WHERE id=?", (tid,)).fetchone()
        if row:
            if row["tipe"] == "masuk":
                con.execute("UPDATE bahan_baku SET stok=MAX(0, stok-?) WHERE id=?", (row["jumlah"], row["bahan_id"]))
            else:
                con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (row["jumlah"], row["bahan_id"]))
        con.execute("DELETE FROM transaksi_bahan WHERE id=?", (tid,))
        con.commit()
        con.close()

    def list_transaksi_bahan(self, bahan_id: int = 0) -> list[dict]:
        con = self._conn()
        if bahan_id:
            rows = con.execute(
                "SELECT t.*, b.nama as bahan_nama, b.satuan FROM transaksi_bahan t JOIN bahan_baku b ON b.id=t.bahan_id WHERE t.bahan_id=? ORDER BY t.tanggal DESC, t.id DESC",
                (bahan_id,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT t.*, b.nama as bahan_nama, b.satuan FROM transaksi_bahan t JOIN bahan_baku b ON b.id=t.bahan_id ORDER BY t.tanggal DESC, t.id DESC LIMIT 200"
            ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    # ── Dashboard Stats ───────────────────────────────────────────────────────

    def get_dashboard_stats(self, bulan: str) -> dict:
        con = self._conn()
        # Panen = total kg dari penjualan jamur
        total_panen    = float(con.execute("SELECT COALESCE(SUM(berat_kg),0) FROM penjualan WHERE tanggal LIKE ?", (f"{bulan}%",)).fetchone()[0])
        total_jual_jamur = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan WHERE tanggal LIKE ?", (f"{bulan}%",)).fetchone()[0])
        total_jual_baglog = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan_baglog WHERE tanggal LIKE ?", (f"{bulan}%",)).fetchone()[0])
        total_beli     = float(con.execute("SELECT COALESCE(SUM(total),0) FROM pembelian_bahan WHERE tanggal LIKE ?", (f"{bulan}%",)).fetchone()[0])
        total_ops      = float(con.execute("SELECT COALESCE(SUM(nominal),0) FROM biaya_operasional WHERE tanggal LIKE ?", (f"{bulan}%",)).fetchone()[0])
        batch_inkubasi = con.execute("SELECT COUNT(*) FROM batches WHERE status='inkubasi'").fetchone()[0]
        batch_panen    = con.execute("SELECT COUNT(*) FROM batches WHERE status='panen'").fetchone()[0]
        baglog_aktif   = con.execute(
            "SELECT COALESCE(SUM(pb.jumlah_baglog),0) FROM pengisian_baglog pb JOIN batches b ON b.id=pb.batch_id WHERE b.status NOT IN ('selesai')"
        ).fetchone()[0]
        con.close()
        total_jual   = total_jual_jamur + total_jual_baglog
        total_keluar = total_beli + total_ops
        laba = total_jual - total_keluar
        return {
            "panen_kg": total_panen,
            "penjualan": total_jual,
            "penjualan_jamur": total_jual_jamur,
            "penjualan_baglog": total_jual_baglog,
            "pengeluaran": total_keluar,
            "laba": laba,
            "batch_inkubasi": batch_inkubasi,
            "batch_panen": batch_panen,
            "baglog_aktif": int(baglog_aktif),
        }

    def get_panen_chart(self, tahun: str) -> list[dict]:
        con = self._conn()
        rows = con.execute(
            "SELECT strftime('%m', tanggal) as bulan, SUM(berat_kg) as total FROM panen WHERE tanggal LIKE ? GROUP BY bulan ORDER BY bulan",
            (f"{tahun}%",)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def get_penjualan_chart(self, tahun: str) -> list[dict]:
        con = self._conn()
        rows = con.execute(
            "SELECT strftime('%m', tanggal) as bulan, SUM(total) as total FROM penjualan WHERE tanggal LIKE ? GROUP BY bulan ORDER BY bulan",
            (f"{tahun}%",)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    # ── Analisis ──────────────────────────────────────────────────────────────

    def get_analisis_batch(self, batch_id: str) -> dict:
        con = self._conn()
        batch = dict(con.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone() or {})
        pengisian = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM pengisian_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0] or 0
        total_dibibit = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM inokulasi WHERE batch_id=?", (batch_id,)).fetchone()[0] or 0
        # Panen dari penjualan yang terhubung ke batch ini
        total_panen = float(con.execute("SELECT COALESCE(SUM(berat_kg),0) FROM penjualan WHERE batch_id=?", (batch_id,)).fetchone()[0])
        steril = float(con.execute("SELECT COALESCE(SUM(biaya_bahan_bakar),0) FROM sterilisasi WHERE batch_id=?", (batch_id,)).fetchone()[0])
        total_jual_baglog = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0])
        total_baglog_jual = int(con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM penjualan_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0])
        inkubasi = con.execute("SELECT baglog_gagal, persentase_keberhasilan, jumlah_baglog FROM inkubasi WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        baglog_sukses = (inkubasi["jumlah_baglog"] - inkubasi["baglog_gagal"]) if inkubasi else int(pengisian)
        baglog_kumbung = baglog_sukses - total_baglog_jual
        total_biaya = steril
        biaya_per_baglog = total_biaya / int(pengisian) if pengisian > 0 else 0
        con.close()
        return {
            "batch": batch,
            "jumlah_baglog": int(pengisian),
            "total_dibibit": int(total_dibibit),
            "total_panen_kg": total_panen,
            "total_biaya": total_biaya,
            "biaya_per_baglog": biaya_per_baglog,
            "panen_per_baglog": total_panen / int(pengisian) if pengisian > 0 else 0,
            "total_jual_baglog": total_jual_baglog,
            "total_baglog_jual": total_baglog_jual,
            "baglog_kumbung": max(0, baglog_kumbung),
        }

    def get_analisis_usaha(self, tahun: str) -> dict:
        con = self._conn()

        total_jual_jamur  = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan WHERE tanggal LIKE ?", (f"{tahun}%",)).fetchone()[0])
        total_kg_jual     = float(con.execute("SELECT COALESCE(SUM(berat_kg),0) FROM penjualan WHERE tanggal LIKE ?", (f"{tahun}%",)).fetchone()[0])
        total_jual_baglog = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan_baglog WHERE tanggal LIKE ?", (f"{tahun}%",)).fetchone()[0])
        total_jual        = total_jual_jamur + total_jual_baglog

        # Panen = total kg terjual (panen setiap hari langsung dijual)
        total_panen = total_kg_jual
        total_beli  = float(con.execute("SELECT COALESCE(SUM(total),0) FROM pembelian_bahan WHERE tanggal LIKE ?", (f"{tahun}%",)).fetchone()[0])
        total_ops   = float(con.execute("SELECT COALESCE(SUM(nominal),0) FROM biaya_operasional WHERE tanggal LIKE ?", (f"{tahun}%",)).fetchone()[0])
        total_biaya = total_beli + total_ops
        laba_bersih = total_jual - total_biaya

        harga_rata       = total_jual_jamur / total_kg_jual if total_kg_jual > 0 else 0
        biaya_var_per_kg = total_beli / total_panen if total_panen > 0 else 0
        margin_per_kg    = harga_rata - biaya_var_per_kg
        bep_kg           = total_ops / margin_per_kg if margin_per_kg > 0 else 0
        bep_rupiah       = bep_kg * harga_rata
        roi              = (laba_bersih / total_biaya * 100) if total_biaya > 0 else 0

        total_baglog = int(con.execute(
            "SELECT COALESCE(SUM(pb.jumlah_baglog),0) FROM pengisian_baglog pb JOIN batches b ON b.id=pb.batch_id WHERE b.tanggal_mulai LIKE ?",
            (f"{tahun}%",)
        ).fetchone()[0])
        produktivitas = total_panen / total_baglog if total_baglog > 0 else 0

        batches = con.execute("SELECT * FROM batches WHERE tanggal_mulai LIKE ? ORDER BY tanggal_mulai DESC", (f"{tahun}%",)).fetchall()
        batch_analisis = []
        for b in batches:
            b = dict(b)
            baglog = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM pengisian_baglog WHERE batch_id=?", (b["id"],)).fetchone()[0]
            dibibit = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM inokulasi WHERE batch_id=?", (b["id"],)).fetchone()[0]
            panen  = float(con.execute("SELECT COALESCE(SUM(berat_kg),0) FROM penjualan WHERE batch_id=?", (b["id"],)).fetchone()[0])
            steril = float(con.execute("SELECT COALESCE(SUM(biaya_bahan_bakar),0) FROM sterilisasi WHERE batch_id=?", (b["id"],)).fetchone()[0])
            inkubasi = con.execute("SELECT baglog_gagal, persentase_keberhasilan FROM inkubasi WHERE batch_id=? LIMIT 1", (b["id"],)).fetchone()
            gagal = inkubasi["baglog_gagal"] if inkubasi else 0
            persen_sukses = inkubasi["persentase_keberhasilan"] if inkubasi else 0
            jual_baglog = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan_baglog WHERE batch_id=?", (b["id"],)).fetchone()[0])
            batch_analisis.append({
                "kode": b["kode"], "nama": b["nama"], "status": b["status"],
                "tanggal_mulai": b["tanggal_mulai"],
                "baglog": int(baglog), "dibibit": int(dibibit), "panen_kg": panen,
                "panen_per_baglog": panen / int(baglog) if baglog else 0,
                "baglog_gagal": gagal,
                "persen_sukses": persen_sukses,
                "biaya_steril": steril,
                "jual_baglog": jual_baglog,
            })

        con.close()
        return {
            "tahun": tahun,
            "total_panen_kg": total_panen,
            "total_jual": total_jual,
            "total_jual_jamur": total_jual_jamur,
            "total_jual_baglog": total_jual_baglog,
            "total_biaya": total_biaya,
            "laba_bersih": laba_bersih,
            "harga_rata": harga_rata,
            "biaya_var_per_kg": biaya_var_per_kg,
            "bep_kg": bep_kg,
            "bep_rupiah": bep_rupiah,
            "roi": roi,
            "total_baglog": total_baglog,
            "produktivitas": produktivitas,
            "batch_analisis": batch_analisis,
        }
