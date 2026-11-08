"""Storage — SQLite untuk Sistem Jamur Tiram."""
from __future__ import annotations
import hashlib, sqlite3, time, uuid
from contextlib import contextmanager
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

CREATE TABLE IF NOT EXISTS rencana_jual (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal         TEXT NOT NULL,
    nama_pembeli    TEXT NOT NULL,
    nomor_hp        TEXT DEFAULT '',
    target_kg       REAL DEFAULT 0,
    harga_per_kg    REAL DEFAULT 0,
    catatan         TEXT DEFAULT '',
    status          TEXT DEFAULT 'belum',
    penjualan_id    INTEGER DEFAULT NULL,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS toleransi_absen (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    tanggal     TEXT NOT NULL,
    keterangan  TEXT DEFAULT 'izin',
    created_by  TEXT DEFAULT '',
    created_at  INTEGER NOT NULL,
    UNIQUE(user_id, tanggal)
);

CREATE TABLE IF NOT EXISTS absensi (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL REFERENCES users(id),
    tanggal     TEXT NOT NULL,
    tipe        TEXT NOT NULL,
    waktu       TEXT NOT NULL,
    foto_path   TEXT DEFAULT '',
    latitude    REAL,
    longitude   REAL,
    catatan     TEXT DEFAULT '',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS laporan_harian (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL REFERENCES users(id),
    tanggal     TEXT NOT NULL,
    isi         TEXT NOT NULL,
    created_at  INTEGER NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._db() as con:
            con.executescript(SCHEMA)
            con.commit()
            self._migrate(con)
            self._seed_admin(con)
            self._seed_bahan(con)

    def _migrate(self, con):
        migrations = [
            ("penjualan",    "tipe_jual",           "TEXT DEFAULT 'timbang'"),
            ("penjualan",    "jenis_paket",          "TEXT DEFAULT ''"),
            ("penjualan",    "jumlah_bungkus",       "INTEGER DEFAULT 0"),
            ("penjualan",    "batch_id",             "TEXT DEFAULT NULL"),
            ("transaksi_bahan", "batch_id",          "TEXT DEFAULT NULL"),
            ("sterilisasi",  "jumlah_baglog",        "INTEGER DEFAULT 0"),
            ("sterilisasi",  "carry_over_batch_id",  "TEXT DEFAULT NULL"),
            ("sterilisasi",  "carry_over_jumlah",    "INTEGER DEFAULT 0"),
            ("sterilisasi",  "kode_steril",           "TEXT DEFAULT ''"),
            ("bahan_baku",   "yield_per_unit",        "REAL DEFAULT 0"),
            ("users",        "nomor_wa",              "TEXT DEFAULT ''"),
            ("users",        "nomor_hp",              "TEXT DEFAULT ''"),
            ("users",        "jabatan",               "TEXT DEFAULT ''"),
            ("users",        "gaji_pokok",            "REAL DEFAULT 0"),
            ("users",        "tanggal_masuk_kerja",   "TEXT DEFAULT ''"),
            ("users",        "jam_masuk",             "TEXT DEFAULT '07:30'"),
            ("users",        "jam_pulang",            "TEXT DEFAULT '17:00'"),
            ("laporan_harian", "jenis_kegiatan",     "TEXT DEFAULT ''"),
            ("laporan_harian", "batch_id",           "TEXT DEFAULT NULL"),
            ("laporan_harian", "foto_path",          "TEXT DEFAULT ''"),
            ("laporan_harian", "detail_json",        "TEXT DEFAULT ''"),
        ]
        for tbl, col, defn in migrations:
            try:
                con.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
                con.commit()
            except Exception:
                pass

    def _conn(self):
        con = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA foreign_keys = ON")
        return con

    @contextmanager
    def _db(self):
        """Context manager — koneksi selalu ditutup meski ada exception."""
        con = self._conn()
        try:
            yield con
        finally:
            con.close()

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
        with self._db() as con:
            row = con.execute(
                "SELECT * FROM users WHERE username=? AND password=? AND aktif=1",
                (username, _hash(password))
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM users ORDER BY nama").fetchall()
        return [dict(r) for r in rows]

    def create_user(self, nama: str, username: str, password: str, role: str,
                    nomor_wa: str = "", nomor_hp: str = "", jabatan: str = "",
                    gaji_pokok: float = 0, tanggal_masuk_kerja: str = "",
                    jam_masuk: str = "07:30", jam_pulang: str = "17:00") -> str:
        uid = uuid.uuid4().hex[:8]
        with self._db() as con:
            con.execute(
                "INSERT INTO users (id,nama,username,password,role,aktif,nomor_wa,nomor_hp,jabatan,gaji_pokok,tanggal_masuk_kerja,jam_masuk,jam_pulang,created_at) VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?)",
                (uid, nama, username, _hash(password), role, nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja, jam_masuk, jam_pulang, int(time.time()))
            )
            con.commit()
        return uid

    def update_user(self, uid: str, nama: str, role: str, password: str = "",
                    nomor_wa: str = "", nomor_hp: str = "", jabatan: str = "",
                    gaji_pokok: float = 0, tanggal_masuk_kerja: str = "",
                    jam_masuk: str = "07:30", jam_pulang: str = "17:00"):
        with self._db() as con:
            if password:
                con.execute(
                    "UPDATE users SET nama=?,role=?,password=?,nomor_wa=?,nomor_hp=?,jabatan=?,gaji_pokok=?,tanggal_masuk_kerja=?,jam_masuk=?,jam_pulang=? WHERE id=?",
                    (nama, role, _hash(password), nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja, jam_masuk, jam_pulang, uid))
            else:
                con.execute(
                    "UPDATE users SET nama=?,role=?,nomor_wa=?,nomor_hp=?,jabatan=?,gaji_pokok=?,tanggal_masuk_kerja=?,jam_masuk=?,jam_pulang=? WHERE id=?",
                    (nama, role, nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja, jam_masuk, jam_pulang, uid))
            con.commit()

    def delete_user(self, uid: str):
        with self._db() as con:
            con.execute("DELETE FROM users WHERE id=?", (uid,))
            con.commit()

    # ── Batches ───────────────────────────────────────────────────────────────

    def list_batches(self, status: str = "") -> list[dict]:
        with self._db() as con:
            if status:
                rows = con.execute("SELECT * FROM batches WHERE status=? ORDER BY tanggal_mulai DESC", (status,)).fetchall()
            else:
                rows = con.execute("SELECT * FROM batches ORDER BY tanggal_mulai DESC").fetchall()
        return [dict(r) for r in rows]

    def get_batch(self, bid: str) -> dict | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM batches WHERE id=?", (bid,)).fetchone()
        return dict(row) if row else None

    def create_batch(self, kode: str, nama: str, tanggal_mulai: str) -> str:
        bid = uuid.uuid4().hex[:8]
        with self._db() as con:
            con.execute(
                "INSERT INTO batches (id,kode,nama,tanggal_mulai,status,created_at) VALUES (?,?,?,?,?,?)",
                (bid, kode, nama, tanggal_mulai, "pengadukan", int(time.time()))
            )
            con.commit()
        return bid

    def advance_batch(self, bid: str, to_status: str):
        with self._db() as con:
            con.execute("UPDATE batches SET status=? WHERE id=?", (to_status, bid))
            con.commit()

    def update_batch(self, bid: str, kode: str, nama: str, tanggal_mulai: str, status: str, catatan: str):
        with self._db() as con:
            con.execute(
                "UPDATE batches SET kode=?,nama=?,tanggal_mulai=?,status=?,catatan=? WHERE id=?",
                (kode, nama, tanggal_mulai, status, catatan, bid)
            )
            con.commit()

    def delete_batch(self, bid: str):
        with self._db() as con:
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
        with self._db() as con:
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
        with self._db() as con:
            row = con.execute("SELECT * FROM pengadukan WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        return dict(row) if row else None

    # ── Pengisian Baglog (multi-sesi) ─────────────────────────────────────────

    def list_pengisian(self, batch_id) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM pengisian_baglog WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        return [dict(r) for r in rows]

    def save_pengisian(self, batch_id, tanggal, jumlah_baglog, operator, catatan="",
                       plastik=0, cincin=0, tutup=0):
        batch = self.get_batch(batch_id)
        ket = f"Logging batch {batch['kode'] if batch else batch_id}"
        with self._db() as con:
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
        with self._db() as con:
            con.execute("DELETE FROM pengisian_baglog WHERE id=?", (pid,))
            con.commit()

    # ── Sterilisasi ───────────────────────────────────────────────────────────

    # ── Sterilisasi (multi-sesi) ──────────────────────────────────────────────

    def list_sterilisasi(self, batch_id) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM sterilisasi WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_carry_over_keluar(self, batch_id) -> list[dict]:
        """Daftar baglog yang dikirim keluar dari batch ini ke batch lain (carry-over)."""
        with self._db() as con:
            rows = con.execute(
                """SELECT s.id, s.tanggal, s.carry_over_jumlah as jumlah,
                          s.batch_id as ke_batch_id,
                          b.kode as ke_batch_kode, b.nama as ke_batch_nama
                   FROM sterilisasi s
                   JOIN batches b ON b.id = s.batch_id
                   WHERE s.carry_over_batch_id=? AND s.carry_over_jumlah > 0
                   ORDER BY s.tanggal""",
                (batch_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def total_carry_over_keluar(self, batch_id) -> int:
        """Total baglog yang sudah ditransfer keluar dari batch ini."""
        with self._db() as con:
            row = con.execute(
                "SELECT COALESCE(SUM(carry_over_jumlah),0) as total FROM sterilisasi WHERE carry_over_batch_id=?",
                (batch_id,)
            ).fetchone()
        return int(row["total"]) if row else 0

    def save_sterilisasi(self, batch_id, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya,
                         kayu_bakar_kg=0, carry_over_batch_id=None, carry_over_jumlah=0, kode_steril=""):
        batch = self.get_batch(batch_id)
        ket = f"Sterilisasi batch {batch['kode'] if batch else batch_id}"
        with self._db() as con:
            try:
                con.execute(
                    """INSERT INTO sterilisasi
                       (batch_id,tanggal,jumlah_baglog,jam_mulai,jam_selesai,durasi_jam,suhu,
                        biaya_bahan_bakar,kayu_bakar_kg,carry_over_batch_id,carry_over_jumlah,kode_steril)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (batch_id, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya,
                     kayu_bakar_kg, carry_over_batch_id or None, carry_over_jumlah or 0, kode_steril or "")
                )
                self._deduct_bahan(con, "Kayu Bakar", kayu_bakar_kg, tanggal, ket, batch_id)
                con.commit()
            finally:
                con.close()

    def delete_sterilisasi(self, sid: int):
        with self._db() as con:
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
        with self._db() as con:
            rows = con.execute("SELECT * FROM inokulasi WHERE batch_id=? ORDER BY tanggal, id", (batch_id,)).fetchall()
        return [dict(r) for r in rows]

    def save_inokulasi(self, batch_id, tanggal, jenis_bibit, kode_bibit, jumlah_baglog, catatan="",
                       bibit_botol=0, alkohol_liter=0, karet_pcs=0, koran_lembar=0):
        batch = self.get_batch(batch_id)
        ket = f"Pembibitan batch {batch['kode'] if batch else batch_id}"
        with self._db() as con:
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
        with self._db() as con:
            con.execute("DELETE FROM inokulasi WHERE id=?", (pid,))
            con.commit()

    # ── Inkubasi ──────────────────────────────────────────────────────────────

    def save_inkubasi(self, batch_id, tanggal_mulai, tanggal_selesai, jumlah, gagal):
        persen = round(((jumlah - gagal) / jumlah * 100) if jumlah > 0 else 0, 1)
        with self._db() as con:
            con.execute(
                "INSERT INTO inkubasi (batch_id,tanggal_mulai,tanggal_selesai,jumlah_baglog,baglog_gagal,persentase_keberhasilan) VALUES (?,?,?,?,?,?)",
                (batch_id, tanggal_mulai, tanggal_selesai, jumlah, gagal, persen)
            )
            con.execute("UPDATE batches SET status='panen' WHERE id=? AND status='inkubasi'", (batch_id,))
            con.commit()

    def get_inkubasi(self, batch_id) -> dict | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM inkubasi WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
        return dict(row) if row else None

    # ── Panen ─────────────────────────────────────────────────────────────────

    def list_panen(self, batch_id: str = "") -> list[dict]:
        with self._db() as con:
            if batch_id:
                rows = con.execute(
                    "SELECT p.*, b.kode as batch_kode FROM panen p JOIN batches b ON b.id=p.batch_id WHERE p.batch_id=? ORDER BY p.tanggal DESC",
                    (batch_id,)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT p.*, b.kode as batch_kode FROM panen p JOIN batches b ON b.id=p.batch_id ORDER BY p.tanggal DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def save_panen(self, batch_id, tanggal, berat_kg, kualitas, harga_estimasi, catatan):
        with self._db() as con:
            con.execute(
                "INSERT INTO panen (batch_id,tanggal,berat_kg,kualitas,harga_estimasi,catatan) VALUES (?,?,?,?,?,?)",
                (batch_id, tanggal, berat_kg, kualitas, harga_estimasi, catatan)
            )
            con.commit()

    def delete_panen(self, pid: int):
        with self._db() as con:
            con.execute("DELETE FROM panen WHERE id=?", (pid,))
            con.commit()

    # ── Penjualan Baglog ──────────────────────────────────────────────────────

    def list_penjualan_baglog(self, batch_id: str = "", bulan: str = "") -> list[dict]:
        with self._db() as con:
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
        return [dict(r) for r in rows]

    def save_penjualan_baglog(self, batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, status_bayar, catatan):
        total = jumlah_baglog * harga_per_baglog
        with self._db() as con:
            con.execute(
                "INSERT INTO penjualan_baglog (batch_id,tanggal,nama_pembeli,nomor_hp,jumlah_baglog,harga_per_baglog,total,status_bayar,catatan,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, total, status_bayar, catatan, int(time.time()))
            )
            con.commit()

    def delete_penjualan_baglog(self, pid: int):
        with self._db() as con:
            con.execute("DELETE FROM penjualan_baglog WHERE id=?", (pid,))
            con.commit()

    # ── Penjualan Jamur ───────────────────────────────────────────────────────

    def list_nama_pembeli(self) -> list[str]:
        """Daftar nama pembeli unik dari semua transaksi, urut frekuensi."""
        with self._db() as con:
            rows = con.execute(
                "SELECT nama_pembeli FROM penjualan WHERE nama_pembeli IS NOT NULL AND nama_pembeli != '' "
                "GROUP BY nama_pembeli ORDER BY COUNT(*) DESC LIMIT 100"
            ).fetchall()
        return [r["nama_pembeli"] for r in rows]

    def list_penjualan(self, bulan: str = "", batch_id: str = "") -> list[dict]:
        with self._db() as con:
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
        return [dict(r) for r in rows]

    def save_penjualan(self, tanggal, nama_pembeli, nomor_hp, berat_kg, harga_per_kg, status_bayar, catatan,
                       batch_id=None, tipe_jual="timbang", jenis_paket="", jumlah_bungkus=0):
        total = round(berat_kg * harga_per_kg if tipe_jual == "timbang" else jumlah_bungkus * harga_per_kg, 2)
        with self._db() as con:
            try:
                con.execute(
                    "INSERT INTO penjualan (tanggal,nama_pembeli,nomor_hp,tipe_jual,jenis_paket,jumlah_bungkus,berat_kg,harga_per_kg,total,status_bayar,catatan,batch_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tanggal, nama_pembeli, nomor_hp, tipe_jual, jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg, total, status_bayar, catatan, batch_id or None, int(time.time()))
                )
                con.commit()
            finally:
                con.close()

    def delete_penjualan(self, pid: int):
        with self._db() as con:
            con.execute("DELETE FROM penjualan WHERE id=?", (pid,))
            con.commit()

    def update_penjualan(self, pid: int, tanggal, nama_pembeli, nomor_hp, tipe_jual,
                         jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg,
                         status_bayar, catatan, batch_id=None):
        total = round(berat_kg * harga_per_kg if tipe_jual == "timbang" else jumlah_bungkus * harga_per_kg, 2)
        with self._db() as con:
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
        with self._db() as con:
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
                result = [dict(r) for r in rows]
                for p in result:
                    # Total pembayaran yang sudah masuk untuk pembeli ini
                    total_pembayaran = con.execute(
                        "SELECT COALESCE(SUM(jumlah), 0) FROM pembayaran_piutang WHERE nama_penjual=?",
                        (p["nama_pembeli"],)
                    ).fetchone()[0]
                    # Total transaksi yang sudah dilunasi via sistem pembayaran
                    total_lunas = con.execute(
                        "SELECT COALESCE(SUM(total), 0) FROM penjualan WHERE nama_pembeli=? AND status_bayar='lunas'",
                        (p["nama_pembeli"],)
                    ).fetchone()[0]
                    # Sisa pembayaran yang belum menutup transaksi manapun
                    unapplied = max(0, total_pembayaran - total_lunas)
                    p["total_hutang"] = p["total_hutang"] - unapplied
                return [p for p in result if p["total_hutang"] > 0]
            finally:
                con.close()

    def list_penjualan_hutang(self, nama: str) -> list[dict]:
        """Transaksi hutang untuk satu penjual, urut terlama dulu."""
        with self._db() as con:
            try:
                rows = con.execute(
                    "SELECT p.*, b.kode as batch_kode FROM penjualan p LEFT JOIN batches b ON b.id=p.batch_id WHERE p.nama_pembeli=? AND p.status_bayar='hutang' ORDER BY p.tanggal ASC, p.id ASC",
                    (nama,)
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                con.close()

    def list_pembayaran_piutang(self, nama: str = "") -> list[dict]:
        with self._db() as con:
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
        with self._db() as con:
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
        with self._db() as con:
            try:
                row = con.execute(
                    "SELECT nama_penjual FROM pembayaran_piutang WHERE id=?", (pid,)
                ).fetchone()
                if not row:
                    return
                nama = row["nama_penjual"]
                con.execute("DELETE FROM pembayaran_piutang WHERE id=?", (pid,))
                # Hitung ulang berapa total yang sudah terbayar setelah hapus
                total_bayar = con.execute(
                    "SELECT COALESCE(SUM(jumlah), 0) FROM pembayaran_piutang WHERE nama_penjual=?",
                    (nama,)
                ).fetchone()[0]
                # Reset semua transaksi pembeli ini ke 'hutang', lalu terapkan ulang pembayaran
                con.execute(
                    "UPDATE penjualan SET status_bayar='hutang' WHERE nama_pembeli=? AND status_bayar='lunas'",
                    (nama,)
                )
                sisa = total_bayar
                rows = con.execute(
                    "SELECT id, total FROM penjualan WHERE nama_pembeli=? AND status_bayar='hutang' ORDER BY tanggal ASC, id ASC",
                    (nama,)
                ).fetchall()
                for r in rows:
                    if sisa <= 0:
                        break
                    if sisa >= r["total"]:
                        con.execute("UPDATE penjualan SET status_bayar='lunas' WHERE id=?", (r["id"],))
                        sisa -= r["total"]
                con.commit()
            finally:
                con.close()

    # ── Pembelian Bahan ───────────────────────────────────────────────────────

    def list_pembelian(self, bulan: str = "") -> list[dict]:
        with self._db() as con:
            if bulan:
                rows = con.execute("SELECT * FROM pembelian_bahan WHERE tanggal LIKE ? ORDER BY tanggal DESC", (f"{bulan}%",)).fetchall()
            else:
                rows = con.execute("SELECT * FROM pembelian_bahan ORDER BY tanggal DESC").fetchall()
        return [dict(r) for r in rows]

    def save_pembelian(self, tanggal, nama_bahan, jumlah, satuan, harga_satuan, catatan):
        total = jumlah * harga_satuan
        with self._db() as con:
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
        with self._db() as con:
            con.execute("DELETE FROM pembelian_bahan WHERE id=?", (pid,))
            con.commit()

    # ── Biaya Operasional ─────────────────────────────────────────────────────

    def list_operasional(self, bulan: str = "") -> list[dict]:
        with self._db() as con:
            if bulan:
                rows = con.execute("SELECT * FROM biaya_operasional WHERE tanggal LIKE ? ORDER BY tanggal DESC", (f"{bulan}%",)).fetchall()
            else:
                rows = con.execute("SELECT * FROM biaya_operasional ORDER BY tanggal DESC").fetchall()
        return [dict(r) for r in rows]

    def save_operasional(self, tanggal, kategori, keterangan, nominal):
        with self._db() as con:
            con.execute(
                "INSERT INTO biaya_operasional (tanggal,kategori,keterangan,nominal,created_at) VALUES (?,?,?,?,?)",
                (tanggal, kategori, keterangan, nominal, int(time.time()))
            )
            con.commit()

    def delete_operasional(self, oid: int):
        with self._db() as con:
            con.execute("DELETE FROM biaya_operasional WHERE id=?", (oid,))
            con.commit()

    # ── Bahan Baku & Stok ─────────────────────────────────────────────────────

    def list_bahan(self) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM bahan_baku ORDER BY nama").fetchall()
        return [dict(r) for r in rows]

    def get_bahan(self, bid: int) -> dict | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM bahan_baku WHERE id=?", (bid,)).fetchone()
        return dict(row) if row else None

    def save_bahan(self, nama, satuan, harga_satuan, stok_min, yield_per_unit=0) -> int:
        with self._db() as con:
            cur = con.execute(
                "INSERT INTO bahan_baku (nama,satuan,harga_satuan,stok_min,stok,yield_per_unit,created_at) VALUES (?,?,?,?,0,?,?)",
                (nama, satuan, harga_satuan, stok_min, yield_per_unit, int(time.time()))
            )
            bid = cur.lastrowid
            con.commit()
        return bid

    def update_bahan(self, bid: int, nama: str, satuan: str, harga_satuan: float, stok_min: float, yield_per_unit: float = 0):
        with self._db() as con:
            con.execute(
                "UPDATE bahan_baku SET nama=?,satuan=?,harga_satuan=?,stok_min=?,yield_per_unit=? WHERE id=?",
                (nama, satuan, harga_satuan, stok_min, yield_per_unit, bid)
            )
            con.commit()

    def delete_bahan(self, bid: int):
        with self._db() as con:
            con.execute("DELETE FROM bahan_baku WHERE id=?", (bid,))
            con.commit()

    def stok_masuk(self, bahan_id, tanggal, jumlah, harga_satuan, keterangan):
        total = jumlah * harga_satuan
        with self._db() as con:
            con.execute(
                "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,created_at) VALUES (?,?,'masuk',?,?,?,?,?)",
                (bahan_id, tanggal, jumlah, harga_satuan, total, keterangan, int(time.time()))
            )
            if harga_satuan > 0:
                con.execute("UPDATE bahan_baku SET stok=stok+?, harga_satuan=? WHERE id=?", (jumlah, harga_satuan, bahan_id))
            else:
                con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (jumlah, bahan_id))
            con.commit()

    def stok_keluar(self, bahan_id, tanggal, jumlah, keterangan):
        with self._db() as con:
            con.execute(
                "INSERT INTO transaksi_bahan (bahan_id,tanggal,tipe,jumlah,harga_satuan,total,keterangan,created_at) VALUES (?,?,'keluar',?,0,0,?,?)",
                (bahan_id, tanggal, jumlah, keterangan, int(time.time()))
            )
            con.execute("UPDATE bahan_baku SET stok=MAX(0, stok-?) WHERE id=?", (jumlah, bahan_id))
            con.commit()

    def delete_transaksi_bahan(self, tid: int):
        with self._db() as con:
            # Kembalikan stok sebelum hapus
            row = con.execute("SELECT bahan_id, tipe, jumlah FROM transaksi_bahan WHERE id=?", (tid,)).fetchone()
            if row:
                if row["tipe"] == "masuk":
                    con.execute("UPDATE bahan_baku SET stok=MAX(0, stok-?) WHERE id=?", (row["jumlah"], row["bahan_id"]))
                else:
                    con.execute("UPDATE bahan_baku SET stok=stok+? WHERE id=?", (row["jumlah"], row["bahan_id"]))
            con.execute("DELETE FROM transaksi_bahan WHERE id=?", (tid,))
            con.commit()

    def list_transaksi_bahan(self, bahan_id: int = 0) -> list[dict]:
        with self._db() as con:
            if bahan_id:
                rows = con.execute(
                    "SELECT t.*, b.nama as bahan_nama, b.satuan FROM transaksi_bahan t JOIN bahan_baku b ON b.id=t.bahan_id WHERE t.bahan_id=? ORDER BY t.tanggal DESC, t.id DESC",
                    (bahan_id,)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT t.*, b.nama as bahan_nama, b.satuan FROM transaksi_bahan t JOIN bahan_baku b ON b.id=t.bahan_id ORDER BY t.tanggal DESC, t.id DESC LIMIT 200"
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Dashboard Stats ───────────────────────────────────────────────────────

    def get_dashboard_stats(self, bulan: str) -> dict:
        with self._db() as con:
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
        with self._db() as con:
            rows = con.execute(
                "SELECT strftime('%m', tanggal) as bulan, SUM(berat_kg) as total FROM panen WHERE tanggal LIKE ? GROUP BY bulan ORDER BY bulan",
                (f"{tahun}%",)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_penjualan_chart(self, tahun: str) -> list[dict]:
        with self._db() as con:
            rows = con.execute(
                "SELECT strftime('%m', tanggal) as bulan, SUM(total) as total FROM penjualan WHERE tanggal LIKE ? GROUP BY bulan ORDER BY bulan",
                (f"{tahun}%",)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Analisis ──────────────────────────────────────────────────────────────

    def get_analisis_batch(self, batch_id: str) -> dict:
        with self._db() as con:
            batch = dict(con.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone() or {})
            pengisian = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM pengisian_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0] or 0
            total_dibibit = con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM inokulasi WHERE batch_id=?", (batch_id,)).fetchone()[0] or 0
            # Panen dari penjualan yang terhubung ke batch ini
            total_panen = float(con.execute("SELECT COALESCE(SUM(berat_kg),0) FROM penjualan WHERE batch_id=?", (batch_id,)).fetchone()[0])
            total_omzet = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan WHERE batch_id=?", (batch_id,)).fetchone()[0])
            steril = float(con.execute("SELECT COALESCE(SUM(biaya_bahan_bakar),0) FROM sterilisasi WHERE batch_id=?", (batch_id,)).fetchone()[0])
            total_jual_baglog = float(con.execute("SELECT COALESCE(SUM(total),0) FROM penjualan_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0])
            total_baglog_jual = int(con.execute("SELECT COALESCE(SUM(jumlah_baglog),0) FROM penjualan_baglog WHERE batch_id=?", (batch_id,)).fetchone()[0])
            inkubasi = con.execute("SELECT baglog_gagal, persentase_keberhasilan, jumlah_baglog FROM inkubasi WHERE batch_id=? ORDER BY id DESC LIMIT 1", (batch_id,)).fetchone()
            baglog_sukses = (inkubasi["jumlah_baglog"] - inkubasi["baglog_gagal"]) if inkubasi else int(pengisian)
            baglog_kumbung = baglog_sukses - total_baglog_jual
            total_biaya = steril
            biaya_per_baglog = total_biaya / int(pengisian) if pengisian > 0 else 0
        return {
            "batch": batch,
            "jumlah_baglog": int(pengisian),
            "total_dibibit": int(total_dibibit),
            "total_panen_kg": total_panen,
            "total_omzet": total_omzet,
            "total_biaya": total_biaya,
            "biaya_per_baglog": biaya_per_baglog,
            "panen_per_baglog": total_panen / int(pengisian) if pengisian > 0 else 0,
            "total_jual_baglog": total_jual_baglog,
            "total_baglog_jual": total_baglog_jual,
            "baglog_kumbung": max(0, baglog_kumbung),
        }

    def get_analisis_usaha(self, tahun: str) -> dict:
        with self._db() as con:

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

    # ── Absensi ───────────────────────────────────────────────────────────────

    def save_absen(self, user_id: str, tanggal: str, tipe: str, waktu: str,
                   foto_path: str = "", latitude=None, longitude=None, catatan: str = "") -> int:
        with self._db() as con:
            cur = con.execute(
                "INSERT INTO absensi (user_id,tanggal,tipe,waktu,foto_path,latitude,longitude,catatan,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, tanggal, tipe, waktu, foto_path, latitude, longitude, catatan, int(time.time()))
            )
            con.commit()
            return cur.lastrowid

    def get_absen(self, user_id: str, tanggal: str, tipe: str) -> dict | None:
        with self._db() as con:
            row = con.execute(
                "SELECT a.*, u.nama FROM absensi a JOIN users u ON u.id=a.user_id WHERE a.user_id=? AND a.tanggal=? AND a.tipe=? ORDER BY a.id DESC LIMIT 1",
                (user_id, tanggal, tipe)
            ).fetchone()
        return dict(row) if row else None

    def list_absensi(self, tanggal: str = "", user_id: str = "") -> list[dict]:
        with self._db() as con:
            sql = "SELECT a.*, u.nama, u.role FROM absensi a JOIN users u ON u.id=a.user_id WHERE 1=1"
            params: list = []
            if tanggal:
                sql += " AND a.tanggal=?"
                params.append(tanggal)
            if user_id:
                sql += " AND a.user_id=?"
                params.append(user_id)
            sql += " ORDER BY a.tanggal DESC, a.waktu DESC"
            rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def list_users_aktif(self) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM users WHERE aktif=1 ORDER BY nama").fetchall()
        return [dict(r) for r in rows]

    def get_rekap_kehadiran(self, user_id: str, bulan: str) -> dict:
        """Hitung total hari hadir, terlambat, toleransi dalam sebulan."""
        with self._db() as con:
            rows = con.execute(
                "SELECT tanggal, waktu FROM absensi WHERE user_id=? AND tipe='masuk' AND tanggal LIKE ?",
                (user_id, f"{bulan}%")
            ).fetchall()
            tol_rows = con.execute(
                "SELECT tanggal FROM toleransi_absen WHERE user_id=? AND tanggal LIKE ?",
                (user_id, f"{bulan}%")
            ).fetchall()
        hadir = len(rows)
        terlambat = sum(1 for r in rows if r["waktu"] > "07:30:59")
        toleransi = len(tol_rows)
        return {"hadir": hadir, "terlambat": terlambat, "toleransi": toleransi}

    def get_user(self, uid: str) -> dict | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def save_toleransi(self, user_id: str, tanggal: str, keterangan: str, created_by: str):
        with self._db() as con:
            con.execute(
                "INSERT OR REPLACE INTO toleransi_absen (user_id,tanggal,keterangan,created_by,created_at) VALUES (?,?,?,?,?)",
                (user_id, tanggal, keterangan, created_by, int(time.time()))
            )
            con.commit()

    def delete_toleransi(self, tid: int):
        with self._db() as con:
            con.execute("DELETE FROM toleransi_absen WHERE id=?", (tid,))
            con.commit()

    def get_toleransi(self, user_id: str, tanggal: str) -> dict | None:
        with self._db() as con:
            row = con.execute(
                "SELECT * FROM toleransi_absen WHERE user_id=? AND tanggal=?",
                (user_id, tanggal)
            ).fetchone()
        return dict(row) if row else None

    def list_toleransi_bulan(self, user_id: str, bulan: str) -> list[dict]:
        with self._db() as con:
            rows = con.execute(
                "SELECT * FROM toleransi_absen WHERE user_id=? AND tanggal LIKE ? ORDER BY tanggal",
                (user_id, f"{bulan}%")
            ).fetchall()
        return [dict(r) for r in rows]

    def hitung_hari_kerja(self, bulan: str) -> int:
        """Hitung total hari dalam sebulan (7 hari seminggu, libur nasional ditandai manual)."""
        import calendar
        year, month = map(int, bulan.split("-"))
        _, days_in_month = calendar.monthrange(year, month)
        return days_in_month

    def get_rekap_penggajian(self, user_id: str, bulan: str) -> dict:
        user = self.get_user(user_id)
        if not user:
            return {}
        rekap = self.get_rekap_kehadiran(user_id, bulan)
        hari_kerja = self.hitung_hari_kerja(bulan)
        hadir = rekap["hadir"]
        toleransi = rekap["toleransi"]
        alpha = max(0, hari_kerja - hadir - toleransi)
        gaji_pokok = float(user.get("gaji_pokok") or 0)
        potongan_per_hari = (gaji_pokok / hari_kerja) if hari_kerja > 0 else 0
        total_potongan = alpha * potongan_per_hari
        return {
            "hari_kerja": hari_kerja,
            "hadir": hadir,
            "toleransi": toleransi,
            "alpha": alpha,
            "terlambat": rekap["terlambat"],
            "gaji_pokok": gaji_pokok,
            "potongan_per_hari": potongan_per_hari,
            "total_potongan": total_potongan,
            "gaji_bersih": gaji_pokok - total_potongan,
        }

    def list_users_ketua_tim(self) -> list[dict]:
        with self._db() as con:
            rows = con.execute("SELECT * FROM users WHERE role='ketua_tim' AND aktif=1").fetchall()
        return [dict(r) for r in rows]

    # ── Laporan Harian ────────────────────────────────────────────────────────

    def _save_produksi_from_laporan(self, con, jenis_kegiatan: str, batch_id: str,
                                    tanggal: str, detail: dict):
        row = con.execute("SELECT kode FROM batches WHERE id=?", (batch_id,)).fetchone()
        ket = f"Laporan Harian — {row['kode'] if row else batch_id}"

        if jenis_kegiatan == "Pengadukan Media":
            bekatul = float(detail.get("bekatul_kg") or 0)
            kapur   = float(detail.get("kapur_kg") or 0)
            serbuk_angkong = int(detail.get("serbuk_angkong") or 0)
            con.execute(
                "INSERT INTO pengadukan (batch_id,tanggal,serbuk_gergaji_kg,bekatul_kg,kapur_kg,air_liter,catatan) VALUES (?,?,0,?,?,0,?)",
                (batch_id, tanggal, bekatul, kapur, f"{serbuk_angkong} angkong serbuk kayu")
            )
            self._deduct_bahan(con, "Dedak/Bekatul", bekatul, tanggal, ket, batch_id)
            self._deduct_bahan(con, "Kapur",         kapur,   tanggal, ket, batch_id)
            con.execute("UPDATE batches SET status='pengisian' WHERE id=? AND status='pengadukan'", (batch_id,))

        elif jenis_kegiatan == "Pengisian Baglog":
            jumlah  = int(detail.get("jumlah_baglog") or 0)
            plastik = int(detail.get("plastik_pcs") or 0)
            con.execute(
                "INSERT INTO pengisian_baglog (batch_id,tanggal,jumlah_baglog,operator,catatan,plastik_pcs,cincin_pcs,tutup_pcs) VALUES (?,?,?,'Tim Laporan','',?,0,0)",
                (batch_id, tanggal, jumlah, plastik)
            )
            self._deduct_bahan(con, "Plastik Baglog", plastik, tanggal, ket, batch_id)

        elif jenis_kegiatan == "Sterilisasi":
            jumlah = int(detail.get("jumlah_baglog") or 0)
            kayu   = float(detail.get("kayu_bakar_kg") or 0)
            con.execute(
                "INSERT INTO sterilisasi (batch_id,tanggal,jumlah_baglog,jam_mulai,jam_selesai,durasi_jam,suhu,biaya_bahan_bakar,kayu_bakar_kg) VALUES (?,?,?,'','',0,0,0,?)",
                (batch_id, tanggal, jumlah, kayu)
            )
            self._deduct_bahan(con, "Kayu Bakar", kayu, tanggal, ket, batch_id)

        elif jenis_kegiatan == "Pembibitan (Inokulasi)":
            jumlah      = int(detail.get("jumlah_baglog") or 0)
            bibit       = float(detail.get("bibit_botol") or 0)
            alkohol     = float(detail.get("alkohol_liter") or 0)
            jenis_bibit = str(detail.get("jenis_bibit") or "")
            con.execute(
                "INSERT INTO inokulasi (batch_id,tanggal,jenis_bibit,kode_bibit,jumlah_baglog,catatan,bibit_botol,alkohol_liter,karet_pcs,koran_lembar) VALUES (?,?,?,'',?,'',?,?,0,0)",
                (batch_id, tanggal, jenis_bibit, jumlah, bibit, alkohol)
            )
            self._deduct_bahan(con, "Bibit Jamur", bibit,   tanggal, ket, batch_id)
            self._deduct_bahan(con, "Alkohol",     alkohol, tanggal, ket, batch_id)
            con.execute("UPDATE batches SET status='inkubasi' WHERE id=? AND status IN ('sterilisasi','pengisian')", (batch_id,))

        elif jenis_kegiatan == "Panen Jamur":
            berat    = float(detail.get("berat_kg") or 0)
            kualitas = str(detail.get("kualitas") or "A")
            if berat > 0:
                con.execute(
                    "INSERT INTO panen (batch_id,tanggal,berat_kg,kualitas,harga_estimasi,catatan) VALUES (?,?,?,?,0,'Dari laporan harian')",
                    (batch_id, tanggal, berat, kualitas)
                )

    def save_laporan_harian(self, user_id: str, tanggal: str, isi: str,
                            jenis_kegiatan: str = "", batch_id: str = "",
                            foto_path: str = "", detail: dict | None = None) -> int:
        import json as _json
        detail_json = _json.dumps(detail, ensure_ascii=False) if detail else ""
        with self._db() as con:
            existing = con.execute("SELECT id FROM laporan_harian WHERE user_id=? AND tanggal=?",
                                   (user_id, tanggal)).fetchone()
            if existing:
                updates = "isi=?, jenis_kegiatan=?, batch_id=?, detail_json=?"
                params  = [isi, jenis_kegiatan, batch_id or None, detail_json]
                if foto_path:
                    updates += ", foto_path=?"
                    params.append(foto_path)
                params.append(existing["id"])
                con.execute(f"UPDATE laporan_harian SET {updates} WHERE id=?", params)
                con.commit()
                return existing["id"]
            cur = con.execute(
                "INSERT INTO laporan_harian (user_id,tanggal,isi,jenis_kegiatan,batch_id,foto_path,detail_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, tanggal, isi, jenis_kegiatan, batch_id or None, foto_path, detail_json, int(time.time()))
            )
            lid = cur.lastrowid
            prod_kegiatan = ("Pengadukan Media", "Pengisian Baglog", "Sterilisasi",
                             "Pembibitan (Inokulasi)", "Panen Jamur")
            if batch_id and detail and jenis_kegiatan in prod_kegiatan:
                self._save_produksi_from_laporan(con, jenis_kegiatan, batch_id, tanggal, detail)
            con.commit()
            return lid

    def list_laporan_harian(self, tanggal: str = "") -> list[dict]:
        with self._db() as con:
            if tanggal:
                rows = con.execute(
                    "SELECT l.*, u.nama, u.role FROM laporan_harian l JOIN users u ON u.id=l.user_id WHERE l.tanggal=? ORDER BY l.created_at DESC",
                    (tanggal,)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT l.*, u.nama, u.role FROM laporan_harian l JOIN users u ON u.id=l.user_id ORDER BY l.tanggal DESC, l.created_at DESC LIMIT 100"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_laporan_harian(self, user_id: str, tanggal: str) -> dict | None:
        with self._db() as con:
            row = con.execute("SELECT * FROM laporan_harian WHERE user_id=? AND tanggal=?",
                              (user_id, tanggal)).fetchone()
        return dict(row) if row else None

    # ── Rencana Jual ──────────────────────────────────────────────────────────

    def list_rencana_jual(self, tanggal_mulai: str, tanggal_akhir: str) -> list[dict]:
        with self._db() as con:
            rows = con.execute(
                "SELECT * FROM rencana_jual WHERE tanggal BETWEEN ? AND ? ORDER BY tanggal, id",
                (tanggal_mulai, tanggal_akhir)
            ).fetchall()
        return [dict(r) for r in rows]

    def save_rencana(self, tanggal: str, nama_pembeli: str, nomor_hp: str,
                     target_kg: float, harga_per_kg: float, catatan: str) -> int:
        with self._db() as con:
            cur = con.execute(
                "INSERT INTO rencana_jual (tanggal,nama_pembeli,nomor_hp,target_kg,harga_per_kg,catatan,status,created_at) VALUES (?,?,?,?,?,?,'belum',?)",
                (tanggal, nama_pembeli, nomor_hp, target_kg, harga_per_kg, catatan, int(time.time()))
            )
            con.commit()
            return cur.lastrowid

    def realisasi_rencana(self, rid: int, tanggal: str, nama_pembeli: str, nomor_hp: str,
                          berat_kg: float, harga_per_kg: float, status_bayar: str) -> int:
        total = round(berat_kg * harga_per_kg, 2)
        with self._db() as con:
            cur = con.execute(
                "INSERT INTO penjualan (tanggal,nama_pembeli,nomor_hp,tipe_jual,jenis_paket,jumlah_bungkus,berat_kg,harga_per_kg,total,status_bayar,catatan,batch_id,created_at) VALUES (?,?,?,'timbang','',0,?,?,?,?,'Dari rencana jual',NULL,?)",
                (tanggal, nama_pembeli, nomor_hp, berat_kg, harga_per_kg, total, status_bayar, int(time.time()))
            )
            pid = cur.lastrowid
            con.execute("UPDATE rencana_jual SET status='terealisasi', penjualan_id=? WHERE id=?", (pid, rid))
            con.commit()
            return pid

    def batal_rencana(self, rid: int):
        with self._db() as con:
            con.execute("UPDATE rencana_jual SET status='batal' WHERE id=?", (rid,))
            con.commit()

    def delete_rencana(self, rid: int):
        with self._db() as con:
            con.execute("DELETE FROM rencana_jual WHERE id=?", (rid,))
            con.commit()

    def list_pola_penjualan(self) -> dict:
        """Pola historis per hari dalam seminggu. Key = Python weekday (0=Mon..6=Sun)."""
        with self._db() as con:
            rows = con.execute("""
                SELECT
                    CAST(strftime('%w', tanggal) AS INTEGER) as hari_sqlite,
                    nama_pembeli,
                    MAX(nomor_hp) as nomor_hp,
                    COUNT(*) as frekuensi,
                    ROUND(AVG(berat_kg), 1) as rata_kg,
                    MAX(tanggal) as terakhir_beli
                FROM penjualan
                WHERE nama_pembeli IS NOT NULL AND nama_pembeli != ''
                GROUP BY hari_sqlite, nama_pembeli
                ORDER BY hari_sqlite, frekuensi DESC
            """).fetchall()
        # SQLite %w: 0=Sun,1=Mon,...,6=Sat → Python weekday: 0=Mon,...,6=Sun
        sqlite_to_py = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
        pola: dict[int, list] = {i: [] for i in range(7)}
        for r in rows:
            py_day = sqlite_to_py.get(r["hari_sqlite"], 0)
            pola[py_day].append(dict(r))
        return pola

    def list_nomor_hp_pembeli(self) -> dict:
        """Map nama_pembeli → nomor_hp terbaru."""
        with self._db() as con:
            rows = con.execute(
                "SELECT nama_pembeli, nomor_hp FROM penjualan WHERE nomor_hp IS NOT NULL AND nomor_hp != '' "
                "GROUP BY nama_pembeli ORDER BY MAX(created_at) DESC"
            ).fetchall()
        return {r["nama_pembeli"]: r["nomor_hp"] for r in rows}

    # ── Settings / Permissions ─────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        with self._db() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._db() as con:
            con.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
            con.commit()

    def get_perms_operator(self) -> set:
        raw = self.get_setting("perms_operator", "")
        if not raw:
            return set()
        return {m.strip() for m in raw.split(",") if m.strip()}

    def set_perms_operator(self, menus: list):
        self.set_setting("perms_operator", ",".join(menus))
