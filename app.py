"""Sistem Informasi Produksi dan Keuangan Budidaya Jamur Tiram."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from storage import Storage


class NeedLogin(Exception):
    pass

DB_PATH = str(Path(__file__).parent / "data" / "jamur.db")
db = Storage(DB_PATH)

app = FastAPI(title="Sistem Jamur Tiram")
tpl = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.exception_handler(NeedLogin)
async def need_login_handler(request: Request, exc: NeedLogin):
    return RedirectResponse("/login", status_code=302)

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


def require_login(request: Request) -> dict:
    token = request.cookies.get("session")
    user = SESSIONS.get(token or "")
    if not user:
        raise NeedLogin()
    return user


def _ctx(request: Request, **kw) -> dict:
    now = datetime.now()
    return {"request": request, "now": now, "bulan_nama": BULAN_NAMA, "status_label": STATUS_LABEL, **kw}


def fmt_rp(v) -> str:
    return f"Rp {int(v):,}".replace(",", ".")


tpl.env.filters["rp"] = fmt_rp
tpl.env.filters["float2"] = lambda v: f"{float(v):.1f}"


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
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("session", token, httponly=True, max_age=86400 * 7)
    return resp


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    SESSIONS.pop(token or "", None)
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, bulan: str = ""):
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
    require_login(request)
    db.create_batch(kode.strip(), nama.strip(), tanggal_mulai)
    return RedirectResponse("/batch", status_code=302)


@app.post("/batch/{bid}/edit")
async def batch_edit(request: Request, bid: str, kode: str = Form(...), nama: str = Form(""),
                     tanggal_mulai: str = Form(...), status: str = Form(...), catatan: str = Form("")):
    require_login(request)
    db.update_batch(bid, kode.strip(), nama.strip(), tanggal_mulai, status, catatan)
    return RedirectResponse("/batch", status_code=302)


@app.post("/batch/{bid}/hapus")
async def batch_hapus(request: Request, bid: str):
    require_login(request)
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
    analisis         = db.get_analisis_batch(bid)
    return tpl.TemplateResponse(request, "batch_detail.html", _ctx(
        request, user=user, batch=batch,
        panen_list=panen_list,
        pengisian_list=pengisian_list,
        sterilisasi_list=sterilisasi_list,
        inokulasi_list=inokulasi_list,
        jual_baglog=jual_baglog,
        inkubasi=inkubasi,
        analisis=analisis,
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
    plastik: int = Form(0), cincin: int = Form(0), tutup: int = Form(0)):
    require_login(request)
    db.save_pengisian(bid, tanggal, jumlah_baglog, operator, catatan, plastik, cincin, tutup)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/pengisian/{pid}/hapus")
async def hapus_pengisian(request: Request, bid: str, pid: int):
    require_login(request)
    db.delete_pengisian(pid)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/sterilisasi")
async def save_sterilisasi(request: Request, bid: str,
    tanggal: str = Form(...), jumlah_baglog: int = Form(0),
    jam_mulai: str = Form(""), jam_selesai: str = Form(""),
    durasi: float = Form(0), suhu: float = Form(0), biaya: float = Form(0),
    kayu_bakar_kg: float = Form(0)):
    require_login(request)
    db.save_sterilisasi(bid, tanggal, jumlah_baglog, jam_mulai, jam_selesai, durasi, suhu, biaya, kayu_bakar_kg)
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/sterilisasi/{sid}/hapus")
async def hapus_sterilisasi(request: Request, bid: str, sid: int):
    require_login(request)
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
    return RedirectResponse(f"/batch/{bid}", status_code=302)


@app.post("/batch/{bid}/inokulasi/{pid}/hapus")
async def hapus_inokulasi(request: Request, bid: str, pid: int):
    require_login(request)
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
    require_login(request)
    db.delete_panen(pid)
    return RedirectResponse("/panen", status_code=302)


# ── Penjualan Jamur ────────────────────────────────────────────────────────────

@app.get("/penjualan", response_class=HTMLResponse)
async def penjualan_page(request: Request, bulan: str = ""):
    user = require_login(request)
    now = datetime.now()
    if not bulan:
        bulan = now.strftime("%Y-%m")
    penjualan_list = db.list_penjualan(bulan)
    batches = db.list_batches()
    total = sum(p["total"] for p in penjualan_list)
    total_kg = sum(p["berat_kg"] for p in penjualan_list)
    total_bungkus = sum(p.get("jumlah_bungkus") or 0 for p in penjualan_list)
    resp = tpl.TemplateResponse(request, "penjualan.html", _ctx(
        request, user=user, penjualan_list=penjualan_list,
        batches=batches, bulan=bulan, total=total, total_kg=total_kg,
        total_bungkus=total_bungkus
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
    require_login(request)
    db.save_penjualan(
        tanggal, nama_pembeli, nomor_hp, berat_kg, harga_per_kg,
        status_bayar, catatan, batch_id or None,
        tipe_jual, jenis_paket, jumlah_bungkus
    )
    return RedirectResponse("/penjualan", status_code=302)


@app.post("/penjualan/{pid}/hapus")
async def penjualan_hapus(request: Request, pid: int):
    require_login(request)
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
    require_login(request)
    db.update_penjualan(pid, tanggal, nama_pembeli, nomor_hp, tipe_jual,
                        jenis_paket, jumlah_bungkus, berat_kg, harga_per_kg,
                        status_bayar, catatan, batch_id or None)
    return RedirectResponse("/penjualan", status_code=302)


# ── Penjualan Baglog ───────────────────────────────────────────────────────────

@app.get("/penjualan-baglog", response_class=HTMLResponse)
async def penjualan_baglog_page(request: Request, bulan: str = ""):
    user = require_login(request)
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
    require_login(request)
    db.save_penjualan_baglog(batch_id, tanggal, nama_pembeli, nomor_hp, jumlah_baglog, harga_per_baglog, status_bayar, catatan)
    return RedirectResponse("/penjualan-baglog", status_code=302)


@app.post("/penjualan-baglog/{pid}/hapus")
async def penjualan_baglog_hapus(request: Request, pid: int):
    require_login(request)
    db.delete_penjualan_baglog(pid)
    return RedirectResponse("/penjualan-baglog", status_code=302)


# ── Piutang ────────────────────────────────────────────────────────────────────

@app.get("/piutang", response_class=HTMLResponse)
async def piutang_page(request: Request):
    user = require_login(request)
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
    require_login(request)
    db.save_pembayaran_piutang(nama_penjual, tanggal, jumlah, catatan)
    return RedirectResponse("/piutang", status_code=302)


@app.post("/piutang/bayar/{pid}/hapus")
async def piutang_bayar_hapus(request: Request, pid: int):
    require_login(request)
    db.delete_pembayaran_piutang(pid)
    return RedirectResponse("/piutang", status_code=302)


# ── Keuangan ───────────────────────────────────────────────────────────────────

@app.get("/keuangan", response_class=HTMLResponse)
async def keuangan_page(request: Request, bulan: str = ""):
    user = require_login(request)
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
    require_login(request)
    db.save_pembelian(tanggal, nama_bahan, jumlah, satuan, harga_satuan, catatan)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/pembelian/{pid}/hapus")
async def pembelian_hapus(request: Request, pid: int):
    require_login(request)
    db.delete_pembelian(pid)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/operasional/tambah")
async def operasional_tambah(request: Request,
    tanggal: str = Form(...), kategori: str = Form(""),
    keterangan: str = Form(...), nominal: float = Form(...)):
    require_login(request)
    db.save_operasional(tanggal, kategori, keterangan, nominal)
    return RedirectResponse("/keuangan", status_code=302)


@app.post("/keuangan/operasional/{oid}/hapus")
async def operasional_hapus(request: Request, oid: int):
    require_login(request)
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
    harga_satuan: float = Form(0), stok_min: float = Form(0)):
    require_login(request)
    db.save_bahan(nama.strip(), satuan.strip(), harga_satuan, stok_min)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/edit")
async def stok_edit_bahan(request: Request, bid: int,
    nama: str = Form(...), satuan: str = Form("kg"),
    harga_satuan: float = Form(0), stok_min: float = Form(0)):
    require_login(request)
    db.update_bahan(bid, nama.strip(), satuan.strip(), harga_satuan, stok_min)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/hapus")
async def stok_hapus_bahan(request: Request, bid: int):
    require_login(request)
    db.delete_bahan(bid)
    return RedirectResponse("/stok", status_code=302)


@app.post("/stok/{bid}/masuk")
async def stok_masuk(request: Request, bid: int,
    tanggal: str = Form(...), jumlah: float = Form(...),
    harga_satuan: float = Form(0), keterangan: str = Form("")):
    require_login(request)
    db.stok_masuk(bid, tanggal, jumlah, harga_satuan, keterangan)
    return RedirectResponse(f"/stok?bahan_id={bid}", status_code=302)


@app.post("/stok/{bid}/keluar")
async def stok_keluar(request: Request, bid: int,
    tanggal: str = Form(...), jumlah: float = Form(...),
    keterangan: str = Form("")):
    require_login(request)
    db.stok_keluar(bid, tanggal, jumlah, keterangan)
    return RedirectResponse(f"/stok?bahan_id={bid}", status_code=302)


@app.post("/stok/transaksi/{tid}/hapus")
async def stok_hapus_transaksi(request: Request, tid: int):
    require_login(request)
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
    user = require_login(request)
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
    user = require_login(request)
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
    user = require_login(request)
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    users = db.list_users()
    return tpl.TemplateResponse(request, "users.html", _ctx(request, user=user, users=users))


@app.post("/users/tambah")
async def user_tambah(request: Request, nama: str = Form(...), username: str = Form(...),
                      password: str = Form(...), role: str = Form("operator")):
    user = require_login(request)
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    db.create_user(nama, username, password, role)
    return RedirectResponse("/users", status_code=302)


@app.post("/users/{uid}/edit")
async def user_edit(request: Request, uid: str, nama: str = Form(...),
                    role: str = Form("operator"), password: str = Form("")):
    user = require_login(request)
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    db.update_user(uid, nama, role, password)
    return RedirectResponse("/users", status_code=302)


@app.post("/users/{uid}/hapus")
async def user_hapus(request: Request, uid: str):
    user = require_login(request)
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=302)
    db.delete_user(uid)
    return RedirectResponse("/users", status_code=302)
