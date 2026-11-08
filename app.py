"""Sistem Informasi Produksi dan Keuangan Budidaya Jamur Tiram."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests as http_requests
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from storage import Storage


class NeedLogin(Exception):
    pass


class NeedAdmin(Exception):
    pass


DB_PATH = str(Path(__file__).parent / "data" / "jamur.db")
PHOTOS_DIR = Path(__file__).parent / "data" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

WUZAPI_TOKEN = "admin_1f36c7b8"
WUZAPI_URL = "http://localhost:8080"

db = Storage(DB_PATH)

app = FastAPI(title="Sistem Jamur Tiram")
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")
tpl = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.exception_handler(NeedLogin)
async def need_login_handler(request: Request, exc: NeedLogin):
    return RedirectResponse("/login", status_code=302)


@app.exception_handler(NeedAdmin)
async def need_admin_handler(request: Request, exc: NeedAdmin):
    return RedirectResponse("/dashboard?akses=ditolak", status_code=302)


def _kirim_wa(nomor: str, pesan: str):
    try:
        http_requests.post(
            f"{WUZAPI_URL}/chat/send/text",
            json={"Phone": nomor, "Body": pesan},
            headers={"token": WUZAPI_TOKEN},
            timeout=10,
        )
    except Exception:
        pass


def _reminder_laporan_harian():
    today = datetime.now().strftime("%Y-%m-%d")
    ketua_list = db.list_users_ketua_tim()
    for u in ketua_list:
        nomor = (u.get("nomor_wa") or "").strip()
        if not nomor:
            continue
        existing = db.get_laporan_harian(u["id"], today)
        if not existing:
            _kirim_wa(nomor, f"Halo {u['nama']}, jangan lupa input *Laporan Harian* hari ini ya! Buka: https://tjn.vpntunel.my.id/laporan-harian")


def _reminder_absen_masuk():
    """Jam 07:00 — ingatkan karyawan yang belum absen masuk."""
    today = datetime.now().strftime("%Y-%m-%d")
    for u in db.list_users_aktif():
        if u.get("role") in ("admin", "owner"):
            continue
        nomor = (u.get("nomor_wa") or "").strip()
        if not nomor:
            continue
        if not db.get_absen(u["id"], today, "masuk"):
            _kirim_wa(nomor, f"Halo {u['nama']}, jangan lupa *Absen Masuk* hari ini ya! 👋\nBuka: https://tjn.vpntunel.my.id/absen")


def _kirim_rencana_jual_pagi():
    """Jam 06:30 — kirim ringkasan rencana jual hari ini ke owner/admin."""
    today = datetime.now().strftime("%Y-%m-%d")
    rencana_list = db.list_rencana_jual(today, today)
    if rencana_list:
        lines = [f"📋 *Rencana Jual Hari Ini — {today}*"]
        for r in rencana_list:
            hp = f" | {r['nomor_hp']}" if r.get("nomor_hp") else ""
            lines.append(f"• {r['nama_pembeli']} — {r['target_kg']} kg{hp}")
        pesan = "\n".join(lines)
    else:
        pesan = f"📋 *Rencana Jual {today}*\nBelum ada rencana jual hari ini."
    for u in db.list_users_aktif():
        if u.get("role") in ("admin", "owner"):
            nomor = (u.get("nomor_wa") or "").strip()
            if nomor:
                _kirim_wa(nomor, pesan)


_scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
_scheduler.add_job(_kirim_rencana_jual_pagi, "cron", hour=6,  minute=30)
_scheduler.add_job(_reminder_absen_masuk,    "cron", hour=7,  minute=0)
_scheduler.add_job(_reminder_laporan_harian, "cron", hour=16, minute=30)
_scheduler.start()


@app.on_event("shutdown")
def _shutdown():
    _scheduler.shutdown(wait=False)

BULAN_NAMA = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

STATUS_LABEL = {
    "pengadukan": ("🟡", "Pengadukan"),
    "pengisian":  ("🔵", "Logging Baglog"),
    "sterilisasi":("🔴", "Sterilisasi"),
    "inokulasi":  ("🟣", "Pembibitan"),
    "inkubasi":   ("🟤", "Inkubasi"),
    "panen":      ("🟢", "Siap Panen"),
    "selesai":    ("⚫", "Selesai"),
}

SESSIONS: dict[str, dict] = {}

# Definisi semua menu yang bisa dikonfigurasi untuk pekerja
MENU_DEFS = [
    ("batch_manage",      "Buat / Hapus Batch"),
    ("penjualan",         "Jual Jamur"),
    ("penjualan_baglog",  "Jual Baglog"),
    ("piutang",           "Piutang"),
    ("keuangan",          "Pengeluaran / Pembelian"),
    ("stok_write",        "Stok Masuk / Keluar / Edit"),
    ("laporan",           "Laporan Bulanan"),
    ("analisis",          "Analisis Usaha"),
]


def require_login(request: Request) -> dict:
    token = request.cookies.get("session")
    user = SESSIONS.get(token or "")
    if not user:
        raise NeedLogin()
    return user


def _is_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "owner")


def require_admin(request: Request) -> dict:
    """Hanya admin dan owner yang boleh akses (menu Users)."""
    user = require_login(request)
    if not _is_admin(user):
        raise NeedAdmin()
    return user


def require_perm(request: Request, menu: str) -> dict:
    """Cek permission: admin/owner/ketua_tim selalu boleh; pekerja cek setting."""
    user = require_login(request)
    if _is_ketua_or_admin(user):
        return user
    perms = db.get_perms_operator()
    if menu not in perms:
        raise NeedAdmin()
    return user


def _is_ketua_or_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "owner", "ketua_tim")


def require_ketua(request: Request) -> dict:
    user = require_login(request)
    if not _is_ketua_or_admin(user):
        raise NeedAdmin()
    return user


def _ctx(request: Request, **kw) -> dict:
    now = datetime.now()
    token = request.cookies.get("session")
    cur_user = SESSIONS.get(token or "")
    if cur_user and cur_user.get("role") not in ("admin", "owner"):
        perms = db.get_perms_operator()
    else:
        perms = {k for k, _ in MENU_DEFS}  # admin/owner dapat semua
    is_ketua = _is_ketua_or_admin(cur_user) if cur_user else False
    is_ketua_only = (cur_user.get("role") == "ketua_tim") if cur_user else False
    return {"request": request, "now": now, "bulan_nama": BULAN_NAMA, "status_label": STATUS_LABEL,
            "perms": perms, "is_ketua": is_ketua, "is_ketua_only": is_ketua_only, **kw}


def fmt_rp(v) -> str:
    return f"Rp {int(v):,}".replace(",", ".")


import json as _json
tpl.env.filters["rp"] = fmt_rp
tpl.env.filters["float2"] = lambda v: f"{float(v):.1f}"
tpl.env.filters["fromjson"] = lambda v: _json.loads(v) if v else {}


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, err: str = ""):
    return tpl.TemplateResponse(request, "login.html", {"request": request, "err": err})


@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = db.login(username, password)
    if not user:
        return RedirectResponse("/login?err=Username+atau+password+salah", status_code=302)
    import secrets
    token = secrets.token_hex(24)
    SESSIONS[token] = user
    target = "/laporan-harian" if user.get("role") == "ketua_tim" else "/dashboard"
    resp = RedirectResponse(target, status_code=302)
    resp.set_cookie("session", token, httponly=True, max_age=86400 * 7)
    return resp


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    SESSIONS.pop(token or "", None)
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


# ── Index (Absensi Kiosk Publik) ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("session")
    cur_user = SESSIONS.get(token or "")
    if cur_user:
        return RedirectResponse("/dashboard", status_code=302)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    semua_user = db.list_users_aktif()
    # Absensi hari ini untuk semua user
    absensi_hari_ini = db.list_absensi(tanggal=today)
    sudah_masuk = {a["user_id"] for a in absensi_hari_ini if a["tipe"] == "masuk"}
    sudah_keluar = {a["user_id"] for a in absensi_hari_ini if a["tipe"] == "keluar"}
    # Map waktu aktual absen per user
    absen_masuk_map = {a["user_id"]: a["waktu"] for a in absensi_hari_ini if a["tipe"] == "masuk"}
    absen_keluar_map = {a["user_id"]: a["waktu"] for a in absensi_hari_ini if a["tipe"] == "keluar"}
    karyawan = [u for u in semua_user if u.get("role") not in ("admin", "owner")]
    # Map jam jadwal per user
    jam_map = {u["id"]: {"masuk": u.get("jam_masuk","07:30"), "pulang": u.get("jam_pulang","17:00")} for u in karyawan}
    # Hitung keterlambatan
    def menit_terlambat(waktu_absen: str, jam_jadwal: str) -> int:
        try:
            h1, m1 = map(int, waktu_absen[:5].split(":"))
            h2, m2 = map(int, jam_jadwal.split(":"))
            delta = (h1 * 60 + m1) - (h2 * 60 + m2)
            return max(0, delta)
        except Exception:
            return 0
    terlambat_map = {}
    for uid, waktu in absen_masuk_map.items():
        jam_jadwal = jam_map.get(uid, {}).get("masuk", "07:30")
        terlambat_map[uid] = menit_terlambat(waktu, jam_jadwal)
    return tpl.TemplateResponse(request, "index.html", {
        "request": request, "now": now, "today": today,
        "karyawan": karyawan,
        "sudah_masuk": sudah_masuk,
        "sudah_keluar": sudah_keluar,
        "absen_masuk_map": absen_masuk_map,
        "absen_keluar_map": absen_keluar_map,
        "jam_map": jam_map,
        "terlambat_map": terlambat_map,
    })


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, bulan: str = "", akses: str = ""):
    user = require_login(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    stats = db.get_dashboard_stats(bulan)
    batches = db.list_batches()
    panen_chart = db.get_panen_chart(now.strftime("%Y"))
    jual_chart  = db.get_penjualan_chart(now.strftime("%Y"))

    chart_bulan = [BULAN_NAMA[int(r["bulan"])] for r in panen_chart]
    chart_panen = [r["total"] for r in panen_chart]
    chart_jual  = []
    jual_map = {r["bulan"]: r["total"] for r in jual_chart}
    for r in panen_chart:
        chart_jual.append(jual_map.get(r["bulan"], 0))

    return tpl.TemplateResponse(request, "dashboard.html", _ctx(
        request, user=user, stats=stats, batches=batches[:5],
        bulan=bulan,
        chart_bulan=json.dumps(chart_bulan),
        chart_panen=json.dumps(chart_panen),
        chart_jual=json.dumps(chart_jual),
        akses_ditolak=(akses == "ditolak"),
    ))


# ── Batch Produksi ─────────────────────────────────────────────────────────────

@app.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request, status: str = ""):
    user = require_login(request)
    batches = db.list_batches(status)
    return tpl.TemplateResponse(request, "batch.html", _ctx(request, user=user, batches=batches, filter_status=status))


@app.post("/batch/tambah")
async def batch_tambah(request: Request, kode: str = Form(...), nama: str = Form(""),
                       tanggal_mulai: str = Form(...)):
    require_perm(request, "batch_manage")
    db.create_batch(kode.strip(), nama.strip(), tanggal_mulai)
    return RedirectResponse("/batch", status_code=302)


@app.post("/batch/{bid}/edit")
async def batch_edit(request: Request, bid: str, kode: str = Form(...), nama: str = Form(""),
                     tanggal_mulai: str = Form(...), status: str = Form(...), catatan: str = Form("")):
    require_perm(request, "batch_manage")
    db.update_batch(bid, kode.strip(), nama.strip(), tanggal_mulai, status, catatan)
    return RedirectResponse("/batch", status_code=302)


@app.post("/batch/{bid}/hapus")
async def batch_hapus(request: Request, bid: str):
    require_perm(request, "batch_manage")
    db.delete_batch(bid)
    return RedirectResponse("/batch", status_code=302)


@app.get("/batch/{bid}", response_class=HTMLResponse)
async def batch_detail(request: Request, bid: str):
    user = require_login(request)
    batch = db.get_batch(bid)
    if not batch:
        return RedirectResponse("/batch", status_code=302)
    panen_list       = db.list_panen(bid)
    pengisian_list   = db.list_pengisian(bid)
    sterilisasi_list = db.list_sterilisasi(bid)
    inokulasi_list   = db.list_inokulasi(bid)
    jual_baglog      = db.list_penjualan_baglog(batch_id=bid)
    inkubasi         = db.get_inkubasi(bid)
    analisis              = db.get_analisis_batch(bid)
    all_batches           = [b for b in db.list_batches() if b["id"] != bid]
    carry_over_keluar     = db.list_carry_over_keluar(bid)
    total_co_keluar       = db.total_carry_over_keluar(bid)
    return tpl.TemplateResponse(request, "batch_detail.html", _ctx(
        request, user=user, batch=batch,
        panen_list=panen_list,
        pengisian_list=pengisian_list,
        sterilisasi_list=sterilisasi_list,
        inokulasi_list=inokulasi_list,
        jual_baglog=jual_baglog,
        inkubasi=inkubasi,
        analisis=analisis,
        all_batches=all_batches,
        carry_over_keluar=carry_over_keluar,
        total_co_keluar=total_co_keluar,
    ))


@app.get("/batch/{bid}/laporan", response_class=HTMLResponse)
async def batch_laporan(request: Request, bid: str):
    user = require_login(request)
    batch = db.get_batch(bid)
    if not batch:
        return RedirectResponse("/batch", status_code=302)
    panen_list       = db.list_panen(bid)
    pengisian_list   = db.list_pengisian(bid)
    sterilisasi_list = db.list_sterilisasi(bid)
    inokulasi_list   = db.list_inokulasi(bid)
    jual_baglog      = db.list_penjualan_baglog(batch_id=bid)
    inkubasi         = db.get_inkubasi(bid)
    analisis         = db.get_analisis_batch(bid)
    carry_over_keluar = db.list_carry_over_keluar(bid)
    total_co_keluar  = db.total_carry_over_keluar(bid)
    return tpl.TemplateResponse(request, "batch_laporan.html", _ctx(
        request, user=user, batch=batch,
        panen_list=panen_list,
        pengisian_list=pengisian_list,
        sterilisasi_list=sterilisasi_list,
        inokulasi_list=inokulasi_list,
        jual_baglog=jual_baglog,
        inkubasi=inkubasi,
        analisis=analisis,
        carry_over_keluar=carry_over_keluar,
        total_co_keluar=total_co_keluar,
    ))


# ── Proses Produksi (per batch) ────────────────────────────────────────────────

@app.post("/batch/{bid}/pengadukan")
async def save_pengadukan(request: Request, bid: str,
    tanggal: str = Form(...), serbuk: float = Form(0), bekatul: float = Form(0),
    kapur: float = Form(0), air: float = Form(0), catatan: str = Form("")):
    require_login(request)
    db.save_pengadukan(bid, tanggal, serbuk, bekatul, kapur, air, catatan)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/pengisian")
async def save_pengisian(request: Request, bid: str,
    tanggal: str = Form(...), jumlah_baglog: int = Form(0),
    operator: str = Form(""), catatan: str = Form(""),
    plastik: float = Form(0), cincin: int = Form(0), tutup: int = Form(0)):
    require_login(request)
    db.save_pengisian(bid, tanggal, jumlah_baglog, operator, catatan, plastik, cincin, tutup)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/pengisian/{pid}/hapus")
async def hapus_pengisian(request: Request, bid: str, pid: int):
    require_perm(request, "batch_manage")
    db.delete_pengisian(pid)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/sterilisasi")
async def save_sterilisasi(request: Request, bid: str,
    tanggal: str = Form(...), jumlah_baglog: int = Form(0),
    jam_mulai: str = Form(""), jam_selesai: str = Form(""),
    durasi: float = Form(0), suhu: float = Form(0), biaya: float = Form(0),
    kayu_bakar_kg: float = Form(0),
    carry_over_batch_id: str = Form(""), carry_over_jumlah: int = Form(0),
    kode_steril: str = Form("")):
    require_login(request)
    db.save_sterilisasi(bid, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya,
                        kayu_bakar_kg, carry_over_batch_id or None, carry_over_jumlah, kode_steril.strip())
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/sterilisasi/{sid}/hapus")
async def hapus_sterilisasi(request: Request, bid: str, sid: int):
    require_perm(request, "batch_manage")
    db.delete_sterilisasi(sid)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/inokulasi")
async def save_inokulasi(request: Request, bid: str,
    tanggal: str = Form(...), jenis_bibit: str = Form(""), kode_bibit: str = Form(""),
    jumlah_baglog: int = Form(0), catatan: str = Form(""),
    bibit_botol: float = Form(0), alkohol_liter: float = Form(0),
    karet_pcs: int = Form(0), koran_lembar: int = Form(0)):
    require_login(request)
    db.save_inokulasi(bid, tanggal, jenis_bibit, kode_bibit, jumlah_baglog, catatan,
                      bibit_botol, alkohol_liter, karet_pcs, koran_lembar)
    batch = db.get_batch(bid)
    if batch and batch["status"] == "inokulasi":
        db.advance_batch(bid, "inkubasi")
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/inokulasi/{pid}/hapus")
async def hapus_inokulasi(request: Request, bid: str, pid: int):
    require_perm(request, "batch_manage")
    db.delete_inokulasi(pid)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/inkubasi")
async def save_inkubasi(request: Request, bid: str,
    tanggal_mulai: str = Form(...), tanggal_selesai: str = Form(""),
    jumlah: int = Form(0), gagal: int = Form(0)):
    require_login(request)
    db.save_inkubasi(bid, tanggal_mulai, tanggal_selesai, jumlah, gagal)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/lanjut/{to_status}")
async def batch_lanjut(request: Request, bid: str, to_status: str):
    require_login(request)
    allowed = {"sterilisasi", "inokulasi", "inkubasi", "panen", "selesai"}
    if to_status in allowed:
        db.advance_batch(bid, to_status)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


# ── Panen ──────────────────────────────────────────────────────────────────────

@app.get("/panen", response_class=HTMLResponse)
async def panen_page(request: Request, bulan: str = ""):
    user = require_login(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    panen_list = db.list_panen()
    batches = db.list_batches("panen")
    total_kg = sum(p["berat_kg"] for p in panen_list if p["tanggal"].startswith(bulan))
    return tpl.TemplateResponse(request, "panen.html", _ctx(
        request, user=user, panen_list=panen_list, batches=batches,
        bulan=bulan, total_kg=total_kg
    ))


@app.post("/panen/tambah")
async def panen_tambah(request: Request,
    batch_id: str = Form(...), tanggal: str = Form(...), berat_kg: float = Form(...),
    kualitas: str = Form("A"), harga_estimasi: float = Form(0), catatan: str = Form("")):
    require_login(request)
    db.save_panen(batch_id, tanggal, berat_kg, kualitas, harga_estimasi, catatan)
    return RedirectResponse("/panen", status_code=302)


@app.post("/panen/{pid}/hapus")
async def panen_hapus(request: Request, pid: int):
    require_perm(request, "batch_manage")
    db.delete_panen(pid)
    return RedirectResponse("/panen", status_code=302)


# ── Penjualan Jamur ────────────────────────────────────────────────────────────

@app.get("/penjualan", response_class=HTMLResponse)
async def penjualan_page(request: Request, bulan: str = ""):
    user = require_perm(request, "penjualan")
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    penjualan_list = db.list_penjualan(bulan)
    batches = db.list_batches()
    total = sum(p["total"] for p in penjualan_list)
    total_kg = sum(p["berat_kg"] for p in penjualan_list)
    total_bungkus = sum(p.get("jumlah_bungkus") or 0 for p in penjualan_list)
    nama_pembeli_list = db.list_nama_pembeli()
    resp = tpl.TemplateResponse(request, "penjualan.html", _ctx(
        request, user=user, penjualan_list=penjualan_list,
        batches=batches, bulan=bulan, total=total, total_kg=total_kg,
        total_bungkus=total_bungkus, nama_pembeli_list=nama_pembeli_list,
    ))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.post("/penjualan/tambah")
async def penjualan_tambah(request: Request,
    tanggal: str = Form(...), nama_pembeli: str = Form(""),
    nomor_hp: str = Form(""), tipe_jual: str = Form("timbang"),
    jenis_paket: str = Form(""), jumlah_bungkus: int = Form(0),
    berat_kg: float = Form(0), harga_per_kg: float = Form(0),
    status_bayar: str = Form("lunas"), catatan: str = Form(""),
    batch_id: str = Form("")):
    require_perm(request, "penjualan")
    db.save_penjualan(
        tanggal, nama_pembeli, nomor_hp, berat_kg, harga_per_kg,
        status_bayar, catatan, batch_id or None,
        tipe_jual, jenis_paket, jumlah_bungkus
    )
    return RedirectResponse("/penjualan", status_code=302)


@app.post("/penjualan/{pid}/hapus")
async def penjualan_hapus(request: Request, pid: int):
    require_perm(request, "penjualan")
    db.delete_penjualan(pid)
    return RedirectResponse("/penjualan", status_code=302)


@app.post("/penjualan/{pid}/edit")
async def penjualan_edit(request: Request, pid: int,
    tanggal: str = Form(...), nama_pembeli: str = Form(""),
    nomor_hp: str = Form(""), tipe_jual: str = Form("timbang"),
    jenis_paket: str = Form(""), jumlah_bungkus: int = Form(0),
    berat_kg: float = Form(0), harga_per_kg: float = Form(0),
    status_bayar: str = Form("lunas"), catatan: str = Form(""),
    batch_id: str = Form("")):
    require_perm(request, "penjualan")
    db.update_penjualan(pid, tanggal, nama_pembeli, nomor_hp, tipe_jual,
                        jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg,
                        status_bayar, catatan, batch_id or None)
    return RedirectResponse("/penjualan", status_code=302)


# ── Penjualan Baglog ───────────────────────────────────────────────────────────

@app.get("/penjualan-baglog", response_class=HTMLResponse)
async def penjualan_baglog_page(request: Request, bulan: str = ""):
    user = require_perm(request, "penjualan_baglog")
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    jual_list = db.list_penjualan_baglog(bulan=bulan)
    batches   = db.list_batches()
    total     = sum(j["total"] for j in jual_list)
    total_baglog = sum(j["jumlah_baglog"] for j in jual_list)
    return tpl.TemplateResponse(request, "penjualan_baglog.html", _ctx(
        request, user=user, jual_list=jual_list, batches=batches,
        bulan=bulan, total=total, total_baglog=total_baglog,
    ))


@app.post("/penjualan-baglog/tambah")
async def penjualan_baglog_tambah(request: Request,
    batch_id: str = Form(...), tanggal: str = Form(...),
    nama_pembeli: str = Form(""), nomor_hp: str = Form(""),
    jumlah_baglog: int = Form(...), harga_per_baglog: float = Form(...),
    status_bayar: str = Form("lunas"), catatan: str = Form("")):
    require_perm(request, "penjualan_baglog")
    db.save_penjualan_baglog(batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, status_bayar, catatan)
    return RedirectResponse("/penjualan-baglog", status_code=302)


@app.post("/penjualan-baglog/{pid}/hapus")
async def penjualan_baglog_hapus(request: Request, pid: int):
    require_perm(request, "penjualan_baglog")
    db.delete_penjualan_baglog(pid)
    return RedirectResponse("/penjualan-baglog", status_code=302)


# ── Piutang ────────────────────────────────────────────────────────────────────

@app.get("/piutang", response_class=HTMLResponse)
async def piutang_page(request: Request):
    user = require_perm(request, "piutang")
    piutang_list = db.list_piutang()
    for p in piutang_list:
        p["hutang_transaksi"] = db.list_penjualan_hutang(p["nama_pembeli"])
        p["pembayaran"] = db.list_pembayaran_piutang(p["nama_pembeli"])
    total_piutang = sum(p["total_hutang"] for p in piutang_list)
    return tpl.TemplateResponse(request, "piutang.html", _ctx(
        request, user=user, piutang_list=piutang_list, total_piutang=total_piutang
    ))


@app.post("/piutang/bayar")
async def piutang_bayar(request: Request,
    nama_penjual: str = Form(...), tanggal: str = Form(...),
    jumlah: float = Form(...), catatan: str = Form("")):
    require_perm(request, "piutang")
    db.save_pembayaran_piutang(nama_penjual, tanggal, jumlah, catatan)
    return RedirectResponse("/piutang", status_code=302)


@app.post("/piutang/bayar/{pid}/hapus")
async def piutang_bayar_hapus(request: Request, pid: int):
    require_perm(request, "piutang")
    db.delete_pembayaran_piutang(pid)
    return RedirectResponse("/piutang", status_code=302)


# ── Keuangan ───────────────────────────────────────────────────────────────────

@app.get("/keuangan", response_class=HTMLResponse)
async def keuangan_page(request: Request, bulan: str = ""):
    user = require_perm(request, "keuangan")
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    pembelian  = db.list_pembelian(bulan)
    operasional = db.list_operasional(bulan)
    bahan_list = db.list_bahan()
    total_beli = sum(p["total"] for p in pembelian)
    total_ops  = sum(o["nominal"] for o in operasional)
    return tpl.TemplateResponse(request, "keuangan.html", _ctx(
        request, user=user, pembelian=pembelian, operasional=operasional,
        bahan_list=bahan_list,
        bulan=bulan, total_beli=total_beli, total_ops=total_ops,
        total_keluar=total_beli + total_ops,
    ))


@app.post("/keuangan/pembelian/tambah")
async def pembelian_tambah(request: Request,
    tanggal: str = Form(...), nama_bahan: str = Form(...),
    jumlah: float = Form(...), satuan: str = Form(""),
    harga_satuan: float = Form(...), catatan: str = Form("")):
    require_perm(request, "keuangan")
    db.save_pembelian(tanggal, nama_bahan, jumlah, satuan, harga_satuan, catatan)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/pembelian/{pid}/hapus")
async def pembelian_hapus(request: Request, pid: int):
    require_perm(request, "keuangan")
    db.delete_pembelian(pid)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/operasional/tambah")
async def operasional_tambah(request: Request,
    tanggal: str = Form(...), kategori: str = Form(""),
    keterangan: str = Form(...), nominal: float = Form(...)):
    require_perm(request, "keuangan")
    db.save_operasional(tanggal, kategori, keterangan, nominal)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/operasional/{oid}/hapus")
async def operasional_hapus(request: Request, oid: int):
    require_perm(request, "keuangan")
    db.delete_operasional(oid)
    return RedirectResponse("/keuangan", status_code=302)


# ── Stok Bahan Baku ────────────────────────────────────────────────────────────

@app.get("/stok", response_class=HTMLResponse)
async def stok_page(request: Request, bahan_id: int = 0):
    user = require_login(request)
    bahan_list  = db.list_bahan()
    transaksi   = db.list_transaksi_bahan(bahan_id)
    bahan_aktif = db.get_bahan(bahan_id) if bahan_id else None
    return tpl.TemplateResponse(request, "stok.html", _ctx(
        request, user=user, bahan_list=bahan_list,
        transaksi=transaksi, bahan_aktif=bahan_aktif, filter_bahan=bahan_id,
    ))


@app.post("/stok/tambah-bahan")
async def stok_tambah_bahan(request: Request,
    nama: str = Form(...), satuan: str = Form("kg"),
    harga_satuan: float = Form(0), stok_min: float = Form(0),
    yield_per_unit: float = Form(0)):
    require_perm(request, "stok_write")
    db.save_bahan(nama.strip(), satuan.strip(), harga_satuan, stok_min, yield_per_unit)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/edit")
async def stok_edit_bahan(request: Request, bid: int,
    nama: str = Form(...), satuan: str = Form("kg"),
    harga_satuan: float = Form(0), stok_min: float = Form(0),
    yield_per_unit: float = Form(0)):
    require_perm(request, "stok_write")
    db.update_bahan(bid, nama.strip(), satuan.strip(), harga_satuan, stok_min, yield_per_unit)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/hapus")
async def stok_hapus_bahan(request: Request, bid: int):
    require_perm(request, "stok_write")
    db.delete_bahan(bid)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/masuk")
async def stok_masuk_route(request: Request, bid: int,
    tanggal: str = Form(...), jumlah: float = Form(...),
    harga_satuan: float = Form(0), keterangan: str = Form("")):
    require_perm(request, "stok_write")
    db.stok_masuk(bid, tanggal, jumlah, harga_satuan, keterangan)
    return RedirectResponse(f"/stok?bahan_id={bid}", status_code=302)


@app.post("/stok/{bid}/keluar")
async def stok_keluar(request: Request, bid: int,
    tanggal: str = Form(...), jumlah: float = Form(...),
    keterangan: str = Form("")):
    require_perm(request, "stok_write")
    db.stok_keluar(bid, tanggal, jumlah, keterangan)
    return RedirectResponse(f"/stok?bahan_id={bid}", status_code=302)


@app.post("/stok/transaksi/{tid}/hapus")
async def stok_hapus_transaksi(request: Request, tid: int):
    require_perm(request, "stok_write")
    # Get bahan_id before delete for redirect
    con = db._conn()
    row = con.execute("SELECT bahan_id FROM transaksi_bahan WHERE id=?", (tid,)).fetchone()
    con.close()
    bahan_id = row["bahan_id"] if row else 0
    db.delete_transaksi_bahan(tid)
    return RedirectResponse(f"/stok?bahan_id={bahan_id}", status_code=302)


# ── Laporan ────────────────────────────────────────────────────────────────────

@app.get("/laporan", response_class=HTMLResponse)
async def laporan_page(request: Request, bulan: str = ""):
    user = require_perm(request, "laporan")
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    stats = db.get_dashboard_stats(bulan)
    penjualan  = db.list_penjualan(bulan)
    pembelian  = db.list_pembelian(bulan)
    operasional = db.list_operasional(bulan)
    panen_list = db.list_panen()
    panen_bulan = [p for p in panen_list if p["tanggal"].startswith(bulan)]
    jual_baglog = db.list_penjualan_baglog(bulan=bulan)
    return tpl.TemplateResponse(request, "laporan.html", _ctx(
        request, user=user, stats=stats, bulan=bulan,
        penjualan=penjualan, pembelian=pembelian,
        operasional=operasional, panen_bulan=panen_bulan,
        jual_baglog=jual_baglog,
    ))


# ── Analisis Usaha ────────────────────────────────────────────────────────────

@app.get("/analisis", response_class=HTMLResponse)
async def analisis_page(request: Request, tahun: str = ""):
    user = require_perm(request, "analisis")
    now = datetime.now()
    if not tahun:
        tahun = now.strftime("%Y")
    data = db.get_analisis_usaha(tahun)
    return tpl.TemplateResponse(request, "analisis.html", _ctx(
        request, user=user, data=data, tahun=tahun
    ))


# ── Users (Admin only) ─────────────────────────────────────────────────────────

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    user = require_admin(request)
    users = db.list_users()
    return tpl.TemplateResponse(request, "users.html", _ctx(request, user=user, users=users))


@app.post("/users/{uid}/hapus")
async def user_hapus(request: Request, uid: str):
    require_admin(request)
    db.delete_user(uid)
    return RedirectResponse("/users", status_code=302)


@app.get("/admin/permissions", response_class=HTMLResponse)
async def permissions_page(request: Request):
    user = require_admin(request)
    perms = db.get_perms_operator()
    return tpl.TemplateResponse(request, "permissions.html", _ctx(
        request, user=user, perms=perms, menu_defs=MENU_DEFS
    ))


@app.post("/admin/permissions")
async def permissions_save(request: Request):
    require_admin(request)
    form = await request.form()
    checked = form.getlist("perm")
    valid = {k for k, _ in MENU_DEFS}
    menus = [m for m in checked if m in valid]
    db.set_perms_operator(menus)
    return RedirectResponse("/admin/permissions?ok=1", status_code=302)


# ── Karyawan (SDM) ────────────────────────────────────────────────────────────

@app.get("/karyawan", response_class=HTMLResponse)
async def karyawan_page(request: Request, bulan: str = ""):
    user = require_admin(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    semua = db.list_users_aktif()
    karyawan = [u for u in semua if u.get("role") not in ("admin", "owner")]
    for k in karyawan:
        k["rekap"] = db.get_rekap_kehadiran(k["id"], bulan)
    return tpl.TemplateResponse(request, "karyawan.html", _ctx(
        request, user=user, karyawan=karyawan, bulan=bulan,
    ))


@app.post("/karyawan/tambah")
async def karyawan_tambah(request: Request,
                          nama: str = Form(...), username: str = Form(...),
                          password: str = Form(...), role: str = Form("operator"),
                          nomor_hp: str = Form(""), nomor_wa: str = Form(""),
                          jabatan: str = Form(""), gaji_pokok: float = Form(0),
                          tanggal_masuk_kerja: str = Form(""),
                          jam_masuk: str = Form("07:30"), jam_pulang: str = Form("17:00")):
    require_admin(request)
    db.create_user(nama, username, password, role, nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja, jam_masuk, jam_pulang)
    return RedirectResponse("/karyawan", status_code=302)


@app.post("/karyawan/{uid}/edit")
async def karyawan_edit(request: Request, uid: str,
                        nama: str = Form(...), role: str = Form("operator"),
                        password: str = Form(""), nomor_hp: str = Form(""),
                        nomor_wa: str = Form(""), jabatan: str = Form(""),
                        gaji_pokok: float = Form(0), tanggal_masuk_kerja: str = Form(""),
                        jam_masuk: str = Form("07:30"), jam_pulang: str = Form("17:00")):
    require_admin(request)
    db.update_user(uid, nama, role, password, nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja, jam_masuk, jam_pulang)
    return RedirectResponse("/karyawan", status_code=302)


@app.post("/karyawan/{uid}/hapus")
async def karyawan_hapus(request: Request, uid: str):
    require_admin(request)
    db.delete_user(uid)
    return RedirectResponse("/karyawan", status_code=302)


# ── Penggajian ────────────────────────────────────────────────────────────────

@app.get("/penggajian", response_class=HTMLResponse)
async def penggajian_page(request: Request, bulan: str = ""):
    user = require_admin(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    semua = db.list_users_aktif()
    karyawan = [u for u in semua if u.get("role") not in ("admin", "owner")]
    for k in karyawan:
        k["gaji"] = db.get_rekap_penggajian(k["id"], bulan)
    total_gaji = sum(k["gaji"].get("gaji_bersih", 0) for k in karyawan)
    return tpl.TemplateResponse(request, "penggajian.html", _ctx(
        request, user=user, karyawan=karyawan, bulan=bulan, total_gaji=total_gaji,
    ))


@app.get("/penggajian/{uid}", response_class=HTMLResponse)
async def penggajian_detail(request: Request, uid: str, bulan: str = ""):
    user = require_admin(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    karyawan = db.get_user(uid)
    if not karyawan:
        return RedirectResponse("/penggajian", status_code=302)
    gaji = db.get_rekap_penggajian(uid, bulan)
    toleransi_list = db.list_toleransi_bulan(uid, bulan)
    toleransi_map = {t["tanggal"]: t for t in toleransi_list}
    # Ambil semua hari masuk bulan ini
    con = db._conn()
    absen_list = con.execute(
        "SELECT tanggal, waktu FROM absensi WHERE user_id=? AND tipe='masuk' AND tanggal LIKE ? ORDER BY tanggal",
        (uid, f"{bulan}%")
    ).fetchall()
    con.close()
    absen_map = {a["tanggal"]: a["waktu"][:5] for a in absen_list}
    return tpl.TemplateResponse(request, "penggajian_detail.html", _ctx(
        request, user=user, karyawan=karyawan, bulan=bulan,
        gaji=gaji, toleransi_map=toleransi_map, absen_map=absen_map,
    ))


@app.post("/penggajian/{uid}/toleransi/tambah")
async def toleransi_tambah(request: Request, uid: str,
    tanggal: str = Form(...), keterangan: str = Form("izin"), bulan: str = Form("")):
    user = require_admin(request)
    db.save_toleransi(uid, tanggal, keterangan, user["id"])
    return RedirectResponse(f"/penggajian/{uid}?bulan={bulan or tanggal[:7]}", status_code=302)


@app.post("/penggajian/{uid}/toleransi/{tid}/hapus")
async def toleransi_hapus(request: Request, uid: str, tid: int, bulan: str = Form("")):
    require_admin(request)
    db.delete_toleransi(tid)
    return RedirectResponse(f"/penggajian/{uid}?bulan={bulan}", status_code=302)


# ── Users: update with nomor_wa support ───────────────────────────────────────

@app.post("/users/tambah")
async def user_tambah_v2(request: Request, nama: str = Form(...), username: str = Form(...),
                         password: str = Form(...), role: str = Form("operator"),
                         nomor_wa: str = Form("")):
    require_admin(request)
    db.create_user(nama, username, password, role, nomor_wa)
    return RedirectResponse("/users", status_code=302)


@app.post("/users/{uid}/edit")
async def user_edit_v2(request: Request, uid: str, nama: str = Form(...),
                       role: str = Form("operator"), password: str = Form(""),
                       nomor_wa: str = Form(""), nomor_hp: str = Form(""),
                       jabatan: str = Form(""), gaji_pokok: float = Form(0),
                       tanggal_masuk_kerja: str = Form("")):
    require_admin(request)
    db.update_user(uid, nama, role, password, nomor_wa, nomor_hp, jabatan, gaji_pokok, tanggal_masuk_kerja)
    return RedirectResponse("/users", status_code=302)


# ── Absensi Kiosk (publik, tidak perlu login) ─────────────────────────────────

@app.post("/absen/kiosk")
async def absen_kiosk(request: Request,
                      user_id: str = Form(...),
                      tipe: str = Form(...),
                      foto: UploadFile = File(None),
                      latitude: str = Form(""),
                      longitude: str = Form("")):
    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    waktu = now.strftime("%H:%M:%S")

    if tipe not in ("masuk", "keluar"):
        return RedirectResponse("/?err=invalid", status_code=302)

    existing = db.get_absen(user_id, tanggal, tipe)
    if existing:
        return RedirectResponse(f"/?err=sudah_{tipe}&uid={user_id}", status_code=302)

    foto_path = ""
    if foto and foto.filename:
        ext = Path(foto.filename).suffix.lower() or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        dest = PHOTOS_DIR / fname
        with open(dest, "wb") as f:
            shutil.copyfileobj(foto.file, f)
        foto_path = fname

    lat = float(latitude) if latitude else None
    lon = float(longitude) if longitude else None
    db.save_absen(user_id, tanggal, tipe, waktu, foto_path, lat, lon)
    return RedirectResponse(f"/?ok={tipe}&uid={user_id}", status_code=302)


# ── Absensi ───────────────────────────────────────────────────────────────────

@app.get("/absen", response_class=HTMLResponse)
async def absen_page(request: Request, tanggal: str = ""):
    user = require_login(request)
    today = datetime.now().strftime("%Y-%m-%d")
    if not tanggal:
        tanggal = today
    absen_masuk = db.get_absen(user["id"], tanggal, "masuk")
    absen_keluar = db.get_absen(user["id"], tanggal, "keluar")
    riwayat = db.list_absensi(user_id=user["id"])[:14]
    return tpl.TemplateResponse(request, "absensi.html", _ctx(
        request, user=user, tanggal=tanggal, today=today,
        absen_masuk=absen_masuk, absen_keluar=absen_keluar,
        riwayat=riwayat,
    ))


@app.post("/absen/masuk")
async def absen_masuk(request: Request,
                      foto: UploadFile = File(None),
                      latitude: str = Form(""),
                      longitude: str = Form(""),
                      catatan: str = Form("")):
    user = require_login(request)
    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    waktu = now.strftime("%H:%M:%S")

    # Cek sudah absen masuk hari ini
    existing = db.get_absen(user["id"], tanggal, "masuk")
    if existing:
        return RedirectResponse("/absen?err=sudah_masuk", status_code=302)

    foto_path = ""
    if foto and foto.filename:
        ext = Path(foto.filename).suffix.lower() or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        dest = PHOTOS_DIR / fname
        with open(dest, "wb") as f:
            shutil.copyfileobj(foto.file, f)
        foto_path = fname

    lat = float(latitude) if latitude else None
    lon = float(longitude) if longitude else None
    db.save_absen(user["id"], tanggal, "masuk", waktu, foto_path, lat, lon, catatan)
    return RedirectResponse("/absen?ok=masuk", status_code=302)


@app.post("/absen/keluar")
async def absen_keluar(request: Request,
                       foto: UploadFile = File(None),
                       latitude: str = Form(""),
                       longitude: str = Form(""),
                       catatan: str = Form("")):
    user = require_login(request)
    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    waktu = now.strftime("%H:%M:%S")

    existing = db.get_absen(user["id"], tanggal, "keluar")
    if existing:
        return RedirectResponse("/absen?err=sudah_keluar", status_code=302)

    foto_path = ""
    if foto and foto.filename:
        ext = Path(foto.filename).suffix.lower() or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        dest = PHOTOS_DIR / fname
        with open(dest, "wb") as f:
            shutil.copyfileobj(foto.file, f)
        foto_path = fname

    lat = float(latitude) if latitude else None
    lon = float(longitude) if longitude else None
    db.save_absen(user["id"], tanggal, "keluar", waktu, foto_path, lat, lon, catatan)
    return RedirectResponse("/absen?ok=keluar", status_code=302)


@app.get("/absen/admin", response_class=HTMLResponse)
async def absen_admin(request: Request, tanggal: str = ""):
    require_admin(request)
    user = require_login(request)
    today = datetime.now().strftime("%Y-%m-%d")
    if not tanggal:
        tanggal = today
    absensi_list = db.list_absensi(tanggal=tanggal)
    semua_user = db.list_users_aktif()

    # kelompokkan per user
    absen_map: dict = {}
    for a in absensi_list:
        uid = a["user_id"]
        if uid not in absen_map:
            absen_map[uid] = {"nama": a["nama"], "masuk": None, "keluar": None}
        absen_map[uid][a["tipe"]] = a

    return tpl.TemplateResponse(request, "absensi_admin.html", _ctx(
        request, user=user, tanggal=tanggal, today=today,
        absen_map=absen_map, semua_user=semua_user,
    ))


# ── Laporan Harian ────────────────────────────────────────────────────────────

JENIS_KEGIATAN = [
    "Pengadukan Media",
    "Pengisian Baglog",
    "Sterilisasi",
    "Pembibitan (Inokulasi)",
    "Inkubasi / Pengecekan",
    "Penyiraman",
    "Kebersihan & Sanitasi",
    "Lainnya",
]


@app.get("/laporan-harian", response_class=HTMLResponse)
async def laporan_harian_page(request: Request, tanggal: str = ""):
    user = require_ketua(request)
    today = datetime.now().strftime("%Y-%m-%d")
    if not tanggal:
        tanggal = today
    laporan_list = db.list_laporan_harian(tanggal)
    my_laporan = db.get_laporan_harian(user["id"], tanggal)
    batches = db.list_batches()
    bahan_stok = {b["nama"]: b for b in db.list_bahan()}
    return tpl.TemplateResponse(request, "laporan_harian.html", _ctx(
        request, user=user, tanggal=tanggal, today=today,
        laporan_list=laporan_list, my_laporan=my_laporan,
        batches=batches, jenis_kegiatan=JENIS_KEGIATAN,
        bahan_stok=bahan_stok,
    ))


# ── Rencana Jual Jamur ────────────────────────────────────────────────────────

HARI_NAMA = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


@app.get("/rencana-jual", response_class=HTMLResponse)
async def rencana_jual_page(request: Request, minggu: str = ""):
    user = require_perm(request, "penjualan")
    today = datetime.now().date()
    if minggu:
        try:
            base = datetime.strptime(minggu, "%Y-%m-%d").date()
        except ValueError:
            base = today
    else:
        base = today
    # Geser ke Senin minggu ini
    senin = base - timedelta(days=base.weekday())
    minggu_akhir = senin + timedelta(days=6)

    tanggal_mulai = senin.strftime("%Y-%m-%d")
    tanggal_akhir = minggu_akhir.strftime("%Y-%m-%d")
    prev_minggu = (senin - timedelta(days=7)).strftime("%Y-%m-%d")
    next_minggu = (senin + timedelta(days=7)).strftime("%Y-%m-%d")

    rencana_list = db.list_rencana_jual(tanggal_mulai, tanggal_akhir)
    pola = db.list_pola_penjualan()
    nomor_hp_map = db.list_nomor_hp_pembeli()
    nama_pembeli_list = db.list_nama_pembeli()

    # Susun per hari (0=Senin..6=Minggu)
    hari_list = []
    for i in range(7):
        tgl = senin + timedelta(days=i)
        tgl_str = tgl.strftime("%Y-%m-%d")
        rencana_hari = [r for r in rencana_list if r["tanggal"] == tgl_str]
        pola_hari = pola.get(i, [])
        hari_list.append({
            "idx": i,
            "nama": HARI_NAMA[i],
            "tanggal": tgl_str,
            "rencana": rencana_hari,
            "pola": pola_hari,
        })

    return tpl.TemplateResponse(request, "rencana_jual.html", _ctx(
        request, user=user,
        hari_list=hari_list,
        tanggal_mulai=tanggal_mulai,
        tanggal_akhir=tanggal_akhir,
        prev_minggu=prev_minggu,
        next_minggu=next_minggu,
        nomor_hp_map=nomor_hp_map,
        nama_pembeli_list=nama_pembeli_list,
    ))


@app.post("/rencana-jual/tambah")
async def rencana_jual_tambah(request: Request,
    tanggal: str = Form(...), nama_pembeli: str = Form(""),
    nomor_hp: str = Form(""), target_kg: float = Form(0),
    harga_per_kg: float = Form(0), catatan: str = Form("")):
    require_perm(request, "penjualan")
    db.save_rencana(tanggal, nama_pembeli.strip(), nomor_hp.strip(), target_kg, harga_per_kg, catatan)
    return RedirectResponse(f"/rencana-jual?minggu={tanggal}", status_code=302)


@app.post("/rencana-jual/{rid}/realisasi")
async def rencana_realisasi(request: Request, rid: int,
    tanggal: str = Form(...), nama_pembeli: str = Form(""),
    nomor_hp: str = Form(""), berat_kg: float = Form(0),
    harga_per_kg: float = Form(0), status_bayar: str = Form("lunas")):
    require_perm(request, "penjualan")
    db.realisasi_rencana(rid, tanggal, nama_pembeli.strip(), nomor_hp.strip(), berat_kg, harga_per_kg, status_bayar)
    return RedirectResponse(f"/rencana-jual?minggu={tanggal}", status_code=302)


@app.post("/rencana-jual/{rid}/batal")
async def rencana_batal_route(request: Request, rid: int, tanggal: str = Form("")):
    require_perm(request, "penjualan")
    db.batal_rencana(rid)
    return RedirectResponse(f"/rencana-jual?minggu={tanggal}", status_code=302)


@app.post("/rencana-jual/{rid}/hapus")
async def rencana_hapus_route(request: Request, rid: int, tanggal: str = Form("")):
    require_perm(request, "penjualan")
    db.delete_rencana(rid)
    return RedirectResponse(f"/rencana-jual?minggu={tanggal}", status_code=302)


@app.post("/laporan-harian/simpan")
async def laporan_harian_simpan(request: Request,
                                 tanggal: str = Form(...),
                                 isi: str = Form(...),
                                 jenis_kegiatan: str = Form(""),
                                 batch_id: str = Form(""),
                                 foto: UploadFile = File(None),
                                 serbuk_angkong: int = Form(0),
                                 bekatul_kg: float = Form(0),
                                 kapur_kg: float = Form(0),
                                 jumlah_baglog: int = Form(0),
                                 plastik_pcs: int = Form(0),
                                 kayu_bakar_kg: float = Form(0),
                                 bibit_botol: float = Form(0),
                                 alkohol_liter: float = Form(0),
                                 jenis_bibit: str = Form(""),
                                 berat_kg: float = Form(0),
                                 kualitas: str = Form("A")):
    user = require_ketua(request)
    foto_path = ""
    if foto and foto.filename:
        ext = Path(foto.filename).suffix.lower() or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        dest = PHOTOS_DIR / fname
        with open(dest, "wb") as f:
            shutil.copyfileobj(foto.file, f)
        foto_path = fname
    detail = {
        "serbuk_angkong": serbuk_angkong,
        "bekatul_kg": bekatul_kg,
        "kapur_kg": kapur_kg,
        "jumlah_baglog": jumlah_baglog,
        "plastik_pcs": plastik_pcs,
        "kayu_bakar_kg": kayu_bakar_kg,
        "bibit_botol": bibit_botol,
        "alkohol_liter": alkohol_liter,
        "jenis_bibit": jenis_bibit,
        "berat_kg": berat_kg,
        "kualitas": kualitas,
    }
    db.save_laporan_harian(user["id"], tanggal, isi, jenis_kegiatan, batch_id, foto_path, detail)
    return RedirectResponse(f"/laporan-harian?tanggal={tanggal}&ok=1", status_code=302)
