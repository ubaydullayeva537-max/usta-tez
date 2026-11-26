import asyncio
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import (
    ADMIN_COOKIE_NAME,
    CLIENT_COOKIE_NAME,
    SESSION_MAX_AGE,
    authenticate_admin,
    authenticate_client,
    create_session_token,
    get_current_admin,
    get_current_client,
    normalize_phone,
)
from app.bot_manager import bot_manager
from app.config import BASE_DIR, IS_VERCEL, SERVICES_IMG_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOADS_DIR, settings
from app.database import (
    STATUS_LABELS,
    create_order,
    db_session,
    get_all_settings,
    get_dashboard_stats,
    get_order,
    get_service,
    hash_password,
    init_db,
    list_masters,
    list_orders,
    list_service_groups,
    list_services,
    set_setting,
    update_order,
)


_lifespan_lock = asyncio.Lock()
_lifespan_users = 0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _lifespan_users
    async with _lifespan_lock:
        if _lifespan_users == 0:
            init_db()
            token = get_all_settings().get("telegram_bot_token", "").strip()
            if token:
                await bot_manager.start(token)
        _lifespan_users += 1
    try:
        yield
    finally:
        async with _lifespan_lock:
            _lifespan_users -= 1
            if _lifespan_users == 0:
                await bot_manager.stop()


app = FastAPI(title=settings.APP_TITLE, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/app/static", StaticFiles(directory=str(STATIC_DIR)), name="app_static")
if IS_VERCEL:
    app.mount("/tmp-uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="tmp_uploads")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/index.html")
async def standalone_index():
    return FileResponse(str(BASE_DIR / "index.html"))


def _format_price(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


templates.env.filters["uzs"] = _format_price


def _save_upload(file: Optional[UploadFile], dest_dir: Path, prefix: str) -> str:
    if not file or not file.filename:
        return ""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    filename = f"{prefix}_{secrets.token_hex(6)}{ext}"
    target = dest_dir / filename
    content = file.file.read()
    if not content:
        return ""
    target.write_bytes(content)
    if dest_dir == SERVICES_IMG_DIR:
        return f"/static/images/services/{filename}"
    if IS_VERCEL:
        return f"/tmp-uploads/{filename}"
    return f"/static/uploads/{filename}"


def _request_port(request: Request) -> Optional[int]:
    if request.url.port:
        return request.url.port
    host_hdr = request.headers.get("host", "")
    if ":" in host_hdr:
        port_part = host_hdr.rsplit(":", 1)[1]
        if port_part.isdigit():
            return int(port_part)
    return None


def _nav_urls(request: Request) -> Dict[str, str]:
    port = _request_port(request)
    hostname = request.url.hostname or "127.0.0.1"
    if port in {settings.PORT, settings.CLIENT_PORT, settings.ADMIN_PORT}:
        return {
            "site_url": f"http://{hostname}:{settings.PORT}/",
            "client_url": f"http://{hostname}:{settings.CLIENT_PORT}/",
            "admin_url": f"http://{hostname}:{settings.ADMIN_PORT}/",
        }
    return {
        "site_url": "/",
        "client_url": "/client",
        "admin_url": "/admin",
    }


def _require_admin_api(request: Request) -> Dict[str, Any]:
    admin = get_current_admin(request)
    if not admin:
        raise HTTPException(status_code=401, detail="Admin autentifikatsiyasi talab qilinadi")
    return admin


# ========================
# WEB PAGES — CLIENT PANEL
# ========================

@app.get("/", response_class=HTMLResponse)
async def root_dispatch(request: Request, phone: Optional[str] = None):
    port = _request_port(request)
    if port == settings.CLIENT_PORT:
        return await client_panel(request, phone=phone)
    if port == settings.ADMIN_PORT:
        return await admin_panel(request)
    return await client_home(request)


async def client_home(request: Request):
    services = list_services(active_only=True)
    groups = list_service_groups(active_only=True)
    masters = list_masters()
    cfg = get_all_settings()
    client = get_current_client(request)
    admin = get_current_admin(request)
    return templates.TemplateResponse(
        request,
        "client_home.html",
        {
            "services": services,
            "groups": groups,
            "masters": masters,
            "cfg": cfg,
            "client": client,
            "admin": admin,
            "bot_status": bot_manager.status(),
            "nav": _nav_urls(request),
        },
    )


@app.get("/client", response_class=HTMLResponse)
async def client_panel(request: Request, phone: Optional[str] = None):
    client = get_current_client(request)
    admin = get_current_admin(request)
    cfg = get_all_settings()
    orders = []
    lookup_phone = ""

    if client:
        orders = list_orders(client_id=client["client_id"], client_phone=client["phone"])
        lookup_phone = client["phone"]
    elif phone:
        lookup_phone = normalize_phone(phone)
        orders = list_orders(client_phone=lookup_phone)

    services = list_services(active_only=True)
    return templates.TemplateResponse(
        request,
        "client_orders.html",
        {
            "client": client,
            "admin": admin,
            "orders": orders,
            "lookup_phone": lookup_phone,
            "status_labels": STATUS_LABELS,
            "services": services,
            "cfg": cfg,
            "nav": _nav_urls(request),
        },
    )


@app.get("/client/login", response_class=HTMLResponse)
async def client_login_page(request: Request):
    nav = _nav_urls(request)
    if get_current_client(request):
        return RedirectResponse(nav["client_url"], status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "mode": "client",
            "cfg": get_all_settings(),
            "error": "",
            "tab": request.query_params.get("tab", "login"),
            "nav": nav,
        },
    )


@app.post("/client/login", response_class=HTMLResponse)
async def client_login_submit(
    request: Request,
    phone: str = Form(...),
    password: str = Form(...),
):
    nav = _nav_urls(request)
    user = authenticate_client(phone, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "mode": "client",
                "cfg": get_all_settings(),
                "error": "Telefon raqam yoki parol noto'g'ri.",
                "tab": "login",
                "nav": nav,
            },
            status_code=401,
        )
    token = create_session_token(user, salt="client-auth")
    resp = RedirectResponse(nav["client_url"], status_code=302)
    resp.set_cookie(
        CLIENT_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.post("/client/register", response_class=HTMLResponse)
async def client_register_submit(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    default_address: str = Form(""),
):
    nav = _nav_urls(request)
    clean_phone = normalize_phone(phone)
    if len(full_name.strip()) < 2 or len(clean_phone) < 9 or len(password) < 4:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "mode": "client",
                "cfg": get_all_settings(),
                "error": "Ism, to'g'ri telefon raqam va kamida 4 belgili parol kiriting.",
                "tab": "register",
                "nav": nav,
            },
            status_code=400,
        )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        exists = conn.execute("SELECT id FROM clients WHERE phone = ?", (clean_phone,)).fetchone()
        if exists:
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "mode": "client",
                    "cfg": get_all_settings(),
                    "error": "Bu telefon raqami allaqachon ro'yxatdan o'tgan. Kirish qismidan kiring.",
                    "tab": "login",
                    "nav": nav,
                },
                status_code=400,
            )
        cur = conn.execute(
            """
            INSERT INTO clients (full_name, phone, password_hash, default_address, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (full_name.strip(), clean_phone, hash_password(password), default_address.strip(), now),
        )
        client_id = cur.lastrowid
        # Attach previous guest orders with this phone
        conn.execute("UPDATE orders SET client_id = ? WHERE client_phone = ? AND client_id IS NULL", (client_id, clean_phone))

    user = {
        "role": "client",
        "client_id": client_id,
        "full_name": full_name.strip(),
        "phone": clean_phone,
        "default_address": default_address.strip(),
    }
    token = create_session_token(user, salt="client-auth")
    resp = RedirectResponse(nav["client_url"], status_code=302)
    resp.set_cookie(CLIENT_COOKIE_NAME, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp


@app.get("/client/logout")
async def client_logout(request: Request):
    resp = RedirectResponse(_nav_urls(request)["site_url"], status_code=302)
    resp.delete_cookie(CLIENT_COOKIE_NAME)
    return resp


# =======================
# WEB PAGES — ADMIN PANEL
# =======================

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    nav = _nav_urls(request)
    if get_current_admin(request):
        return RedirectResponse(nav["admin_url"], status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "mode": "admin",
            "cfg": get_all_settings(),
            "error": "",
            "tab": "login",
            "nav": nav,
        },
    )


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    nav = _nav_urls(request)
    admin = authenticate_admin(username, password)
    if not admin:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "mode": "admin",
                "cfg": get_all_settings(),
                "error": "Admin login yoki parol noto'g'ri.",
                "tab": "login",
                "nav": nav,
            },
            status_code=401,
        )
    token = create_session_token(admin, salt="admin-auth")
    resp = RedirectResponse(nav["admin_url"], status_code=302)
    resp.set_cookie(ADMIN_COOKIE_NAME, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp


@app.get("/admin/logout")
async def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie(ADMIN_COOKIE_NAME)
    return resp


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    admin = get_current_admin(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    stats = get_dashboard_stats()
    orders = list_orders()
    services = list_services(active_only=False)
    groups = list_service_groups(active_only=False)
    masters = list_masters()
    cfg = get_all_settings()

    return templates.TemplateResponse(
        request,
        "admin_panel.html",
        {
            "admin": admin,
            "stats": stats,
            "orders": orders,
            "services": services,
            "groups": groups,
            "masters": masters,
            "cfg": cfg,
            "status_labels": STATUS_LABELS,
            "bot_status": bot_manager.status(),
            "nav": _nav_urls(request),
        },
    )


# ========================
# PUBLIC / CLIENT REST API
# ========================

@app.get("/api/services")
async def api_services(group: Optional[str] = None, search: Optional[str] = None):
    return {"services": list_services(active_only=True, group_name=group, search=search)}


@app.post("/api/orders")
async def api_create_order(
    request: Request,
    service_id: Optional[int] = Form(None),
    service_name: str = Form(""),
    client_name: str = Form(...),
    client_phone: str = Form(...),
    district: str = Form(""),
    address: str = Form(...),
    description: str = Form(""),
    preferred_time: str = Form("Tezda"),
    photo: Optional[UploadFile] = File(None),
):
    clean_phone = normalize_phone(client_phone)
    if len(client_name.strip()) < 2 or len("".join(c for c in clean_phone if c.isdigit())) < 9 or len(address.strip()) < 3:
        raise HTTPException(status_code=400, detail="Ism, telefon raqam va manzilni to'g'ri kiriting.")

    resolved_service_name = service_name.strip()
    if service_id:
        svc = get_service(service_id)
        if svc:
            resolved_service_name = svc["name"]
    if not resolved_service_name:
        resolved_service_name = "Umumiy usta xizmati"

    photo_path = _save_upload(photo, UPLOADS_DIR, "web")
    client = get_current_client(request)
    order = create_order(
        service_id=service_id,
        service_name=resolved_service_name,
        client_name=client_name,
        client_phone=clean_phone,
        district=district,
        address=address,
        description=description,
        preferred_time=preferred_time,
        photo_path=photo_path,
        source="web",
        client_id=client["client_id"] if client else None,
    )
    await bot_manager.notify_new_order(order)
    return {"ok": True, "order": order}


@app.get("/api/orders/track")
async def api_track_orders(phone: str):
    clean = normalize_phone(phone)
    rows = list_orders(client_phone=clean)
    return {"orders": rows, "status_labels": STATUS_LABELS}


@app.post("/api/client/orders/{order_id}/cancel")
async def api_client_cancel_order(request: Request, order_id: int, phone: str = Form("")):
    client = get_current_client(request)
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Ariza topilmadi")

    allowed = False
    if client and (order.get("client_id") == client["client_id"] or order["client_phone"] == client["phone"]):
        allowed = True
    elif phone and normalize_phone(phone) == order["client_phone"]:
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    if order["status"] != "new":
        raise HTTPException(status_code=400, detail="Faqat 'Yangi ariza' holatidagi buyurtmani bekor qilish mumkin")

    updated = update_order(order_id, status="cancelled", admin_note="Mijoz tomonidan bekor qilindi")
    return {"ok": True, "order": updated}


@app.post("/api/client/orders/{order_id}/rate")
async def api_client_rate_order(
    request: Request,
    order_id: int,
    rating: int = Form(...),
    review: str = Form(""),
    phone: str = Form(""),
):
    client = get_current_client(request)
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Ariza topilmadi")

    allowed = False
    if client and (order.get("client_id") == client["client_id"] or order["client_phone"] == client["phone"]):
        allowed = True
    elif phone and normalize_phone(phone) == order["client_phone"]:
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    rating_val = max(1, min(5, rating))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        conn.execute(
            "UPDATE orders SET client_rating = ?, client_review = ?, updated_at = ? WHERE id = ?",
            (rating_val, review.strip(), now, order_id),
        )
    return {"ok": True, "order": get_order(order_id)}


# =================
# ADMIN REST APIs
# =================

@app.get("/api/admin/dashboard")
async def api_admin_dashboard(
    request: Request,
    status: Optional[str] = None,
    service_id: Optional[int] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
):
    _require_admin_api(request)
    return {
        "stats": get_dashboard_stats(),
        "orders": list_orders(status=status, service_id=service_id, source=source, search=search),
        "services": list_services(active_only=False),
        "masters": list_masters(),
        "bot_status": bot_manager.status(),
        "status_labels": STATUS_LABELS,
    }


@app.patch("/api/admin/orders/{order_id}")
async def api_admin_update_order(request: Request, order_id: int):
    _require_admin_api(request)
    payload = await request.json()
    existing = get_order(order_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ariza topilmadi")

    master_raw = payload.get("master_id")
    clear_master = master_raw == "" or master_raw is None and "master_id" in payload
    master_id = int(master_raw) if master_raw not in (None, "", 0, "0") else None

    est_price = payload.get("estimated_price")
    est_price_val = int(est_price) if est_price not in (None, "") else None

    updated = update_order(
        order_id,
        status=payload.get("status"),
        master_id=master_id,
        clear_master=clear_master,
        admin_note=payload.get("admin_note"),
        estimated_price=est_price_val,
    )
    if updated and (updated["status"] != existing["status"] or updated.get("master_id") != existing.get("master_id")):
        await bot_manager.notify_order_status(updated)
    return {"ok": True, "order": updated}


@app.delete("/api/admin/orders/{order_id}")
async def api_admin_delete_order(request: Request, order_id: int):
    _require_admin_api(request)
    with db_session() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    return {"ok": True}


@app.post("/api/admin/services")
async def api_admin_create_service(
    request: Request,
    name: str = Form(...),
    group_name: str = Form(...),
    description: str = Form(...),
    price_from: int = Form(50000),
    unit: str = Form("so'mdan"),
    eta_minutes: int = Form(45),
    is_popular: bool = Form(False),
    image: Optional[UploadFile] = File(None),
):
    _require_admin_api(request)
    base_slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    slug = f"{base_slug or 'xizmat'}-{secrets.token_hex(2)}"
    image_url = _save_upload(image, SERVICES_IMG_DIR, slug) or "/static/images/services/evro-remont.png"
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO services (
                slug, name, group_name, description, price_from, unit,
                eta_minutes, image_url, icon, is_popular, is_active, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'wrench', ?, 1, 200)
            """,
            (slug, name.strip(), group_name.strip(), description.strip(), price_from, unit.strip(), eta_minutes, image_url, 1 if is_popular else 0),
        )
        new_id = cur.lastrowid
    return {"ok": True, "service": get_service(new_id)}


@app.post("/api/admin/services/{service_id}")
async def api_admin_update_service(
    request: Request,
    service_id: int,
    name: str = Form(...),
    group_name: str = Form(...),
    description: str = Form(...),
    price_from: int = Form(...),
    unit: str = Form("so'mdan"),
    eta_minutes: int = Form(45),
    is_popular: bool = Form(False),
    is_active: bool = Form(True),
    image: Optional[UploadFile] = File(None),
):
    _require_admin_api(request)
    svc = get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Xizmat topilmadi")
    image_url = _save_upload(image, SERVICES_IMG_DIR, svc["slug"]) or svc["image_url"]
    with db_session() as conn:
        conn.execute(
            """
            UPDATE services
            SET name = ?, group_name = ?, description = ?, price_from = ?, unit = ?,
                eta_minutes = ?, image_url = ?, is_popular = ?, is_active = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                group_name.strip(),
                description.strip(),
                price_from,
                unit.strip(),
                eta_minutes,
                image_url,
                1 if is_popular else 0,
                1 if is_active else 0,
                service_id,
            ),
        )
    return {"ok": True, "service": get_service(service_id)}


@app.delete("/api/admin/services/{service_id}")
async def api_admin_delete_service(request: Request, service_id: int):
    _require_admin_api(request)
    with db_session() as conn:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    return {"ok": True}


@app.post("/api/admin/masters")
async def api_admin_create_master(request: Request):
    _require_admin_api(request)
    data = await request.json()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO masters (
                full_name, phone, specialty, group_name, experience_years,
                rating, completed_jobs, district, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 4.9, 0, ?, ?, ?)
            """,
            (
                data["full_name"].strip(),
                normalize_phone(data["phone"]),
                data["specialty"].strip(),
                data.get("group_name", "Umumiy").strip(),
                int(data.get("experience_years", 5)),
                data.get("district", "Barcha tumanlar").strip(),
                data.get("status", "available"),
                now,
            ),
        )
        master_id = cur.lastrowid
        row = conn.execute("SELECT * FROM masters WHERE id = ?", (master_id,)).fetchone()
    return {"ok": True, "master": dict(row)}


@app.patch("/api/admin/masters/{master_id}")
async def api_admin_update_master(request: Request, master_id: int):
    _require_admin_api(request)
    data = await request.json()
    with db_session() as conn:
        conn.execute(
            """
            UPDATE masters SET status = ?, district = ?, specialty = ? WHERE id = ?
            """,
            (data.get("status", "available"), data.get("district", "Barcha tumanlar"), data.get("specialty", ""), master_id),
        )
        row = conn.execute("SELECT * FROM masters WHERE id = ?", (master_id,)).fetchone()
    return {"ok": True, "master": dict(row) if row else None}


@app.delete("/api/admin/masters/{master_id}")
async def api_admin_delete_master(request: Request, master_id: int):
    _require_admin_api(request)
    with db_session() as conn:
        conn.execute("DELETE FROM masters WHERE id = ?", (master_id,))
    return {"ok": True}


@app.post("/api/admin/bot/config")
async def api_admin_bot_config(request: Request):
    _require_admin_api(request)
    data = await request.json()
    token = (data.get("telegram_bot_token") or "").strip()
    admin_ids = (data.get("admin_telegram_ids") or "").strip()
    set_setting("telegram_bot_token", token)
    set_setting("admin_telegram_ids", admin_ids)
    if IS_VERCEL and token:
        base_url = str(request.base_url).rstrip("/")
        status = await bot_manager.init_webhook_mode(token, f"{base_url}/api/telegram/webhook")
    else:
        status = await bot_manager.start(token) if token else (await bot_manager.stop() or bot_manager.status())
    return {"ok": True, "bot_status": status}


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    await bot_manager.feed_webhook_update(payload)
    return {"ok": True}


@app.post("/api/admin/bot/stop")
async def api_admin_bot_stop(request: Request):
    _require_admin_api(request)
    await bot_manager.stop()
    return {"ok": True, "bot_status": bot_manager.status()}


@app.post("/api/admin/settings")
async def api_admin_settings(request: Request):
    admin = _require_admin_api(request)
    data = await request.json()
    if data.get("company_name"):
        set_setting("company_name", data["company_name"].strip())
    if data.get("company_phone"):
        set_setting("company_phone", data["company_phone"].strip())
    if data.get("working_hours"):
        set_setting("working_hours", data["working_hours"].strip())
    if data.get("new_password") and len(data["new_password"]) >= 4:
        with db_session() as conn:
            conn.execute(
                "UPDATE admins SET password_hash = ? WHERE id = ?",
                (hash_password(data["new_password"]), admin["admin_id"]),
            )
    return {"ok": True, "cfg": get_all_settings()}
