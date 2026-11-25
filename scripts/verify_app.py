import html
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.config import SERVICES_IMG_DIR, STATIC_DIR
from app.database import create_order, init_db, list_services


def main():
    init_db()
    services = list_services(active_only=False)
    assert len(services) == 30, f"Expected 30 services, got {len(services)}"

    # 1. Verify hero & all 30 service image files exist
    assert (STATIC_DIR / "images" / "hero.jpg").exists(), "hero.jpg missing"
    for svc in services:
        fname = Path(svc["image_url"]).name
        assert (SERVICES_IMG_DIR / fname).exists(), f"Missing image for {svc['slug']}: {fname}"
    print(f"[PASS] Verified hero.jpg and all {len(services)} service images exist on disk.")

    with TestClient(app) as client:
        # 2. Client Home page
        r = client.get("/")
        assert r.status_code == 200
        body = html.unescape(r.text)
        assert "Avto mashina ustalari" in body
        assert "Mangal quruvchi ustasi" in body
        assert "Elektromobil ustasi" in body
        assert "Wi-Fi o'rnatish xizmati" in body
        print("[PASS] Client Home (/) renders all requested services.")

        # 3. Unauthenticated /admin redirects to /admin/login
        r_unauth = client.get("/admin", follow_redirects=False)
        assert r_unauth.status_code == 302 and "/admin/login" in r_unauth.headers["location"]
        r_api_unauth = client.get("/api/admin/dashboard")
        assert r_api_unauth.status_code == 401
        print("[PASS] Admin panel & API are strictly protected from unauthenticated access.")

        # 4. Client Login (separate from Admin)
        r_clogin = client.post(
            "/client/login",
            data={"phone": "+998901234567", "password": "client123"},
            follow_redirects=False,
        )
        assert r_clogin.status_code == 302 and r_clogin.headers["location"] == "/client"
        # Client still cannot access /admin
        assert client.get("/api/admin/dashboard").status_code == 401
        print("[PASS] Client login works and stays isolated from Admin Panel.")

        # 5. Client submits order with uploaded image
        fake_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
        r_order = client.post(
            "/api/orders",
            data={
                "service_id": str(services[0]["id"]),
                "client_name": "Test Mijoz",
                "client_phone": "+998909876543",
                "district": "Yakkasaroy",
                "address": "Shota Rustaveli 22",
                "description": "Test zayavka rasmi bilan",
                "preferred_time": "Tezda",
            },
            files={"photo": ("issue.jpg", fake_img, "image/jpeg")},
        )
        assert r_order.status_code == 200
        created_order = r_order.json()["order"]
        assert created_order["order_code"].startswith("UST-")
        assert created_order["photo_path"].startswith("/static/uploads/")
        print(f"[PASS] Client order created via Web API: {created_order['order_code']} with photo.")

        # 6. Simulate Telegram Bot order in shared DB
        tg_order = create_order(
            service_id=services[1]["id"],
            service_name=services[1]["name"],
            client_name="Telegram Mijoz",
            client_phone="+998931112233",
            address="Chilonzor 5",
            description="Telegram botdan test ariza",
            source="telegram",
            telegram_user_id=123456789,
            telegram_username="tg_user",
        )
        assert tg_order["source"] == "telegram"
        print(f"[PASS] Telegram Bot order created in shared DB: {tg_order['order_code']}.")

        # 7. Admin Login & Dashboard verification
        r_alogin = client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False,
        )
        assert r_alogin.status_code == 302 and r_alogin.headers["location"] == "/admin"

        r_admin_page = client.get("/admin")
        assert r_admin_page.status_code == 200
        assert "Xizmatlar bo'yicha tushgan arizalar" in html.unescape(r_admin_page.text)

        r_dash = client.get("/api/admin/dashboard")
        assert r_dash.status_code == 200
        dash = r_dash.json()
        codes = {o["order_code"] for o in dash["orders"]}
        assert created_order["order_code"] in codes
        assert tg_order["order_code"] in codes
        assert len(dash["stats"]["by_service"]) >= 2
        print("[PASS] Admin Panel displays both Web and Telegram orders + per-service breakdown.")

        # 8. Admin assigns master and updates status
        master_id = dash["masters"][0]["id"]
        r_patch = client.patch(
            f"/api/admin/orders/{created_order['id']}",
            json={"status": "accepted", "master_id": master_id, "admin_note": "Usta yo'lga chiqdi"},
        )
        assert r_patch.status_code == 200
        patched = r_patch.json()["order"]
        assert patched["status"] == "accepted"
        assert patched["master_id"] == master_id

        # 9. Client Panel reflects updated order
        r_track = client.get("/client", params={"phone": "+998909876543"})
        assert r_track.status_code == 200
        track_body = html.unescape(r_track.text)
        assert created_order["order_code"] in track_body
        assert "Qabul qilindi" in track_body

        # 10. Verify Telegram bot handlers module imports cleanly
        from app import bot_handlers, bot_manager
        assert hasattr(bot_handlers, "router")
        assert hasattr(bot_manager, "bot_manager")
        print("[PASS] Telegram bot router and manager verified.")

        # Clean up test orders & test upload so demo DB stays clean
        client.delete(f"/api/admin/orders/{created_order['id']}")
        client.delete(f"/api/admin/orders/{tg_order['id']}")
        uploaded_file = ROOT / "app" / created_order["photo_path"].lstrip("/")
        if uploaded_file.exists():
            uploaded_file.unlink()
        print("[PASS] End-to-end Web + Telegram DB + Admin + Client Panel flow verified!")


if __name__ == "__main__":
    main()
