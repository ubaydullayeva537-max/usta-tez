import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import DB_PATH, settings


STATUS_LABELS = {
    "new": "Yangi ariza",
    "accepted": "Qabul qilindi",
    "on_the_way": "Usta yo'lda",
    "in_progress": "Bajarilmoqda",
    "completed": "Bajarildi",
    "cancelled": "Bekor qilindi",
}

STATUS_ORDER = ["new", "accepted", "on_the_way", "in_progress", "completed", "cancelled"]


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected = stored_hash.split("$", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return hmac.compare_digest(candidate, expected)
    except ValueError:
        return False


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                default_address TEXT DEFAULT '',
                telegram_id INTEGER,
                telegram_username TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                description TEXT NOT NULL,
                price_from INTEGER NOT NULL DEFAULT 50000,
                unit TEXT NOT NULL DEFAULT 'so''mdan',
                eta_minutes INTEGER NOT NULL DEFAULT 45,
                image_url TEXT NOT NULL,
                icon TEXT NOT NULL DEFAULT 'wrench',
                is_popular INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 100
            );

            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                specialty TEXT NOT NULL,
                group_name TEXT NOT NULL,
                experience_years INTEGER NOT NULL DEFAULT 5,
                rating REAL NOT NULL DEFAULT 4.9,
                completed_jobs INTEGER NOT NULL DEFAULT 0,
                district TEXT NOT NULL DEFAULT 'Barcha tumanlar',
                status TEXT NOT NULL DEFAULT 'available',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE NOT NULL,
                service_id INTEGER REFERENCES services(id) ON DELETE SET NULL,
                service_name TEXT NOT NULL,
                master_id INTEGER REFERENCES masters(id) ON DELETE SET NULL,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                client_name TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                district TEXT DEFAULT '',
                address TEXT NOT NULL,
                description TEXT DEFAULT '',
                preferred_time TEXT DEFAULT 'Tezda',
                photo_path TEXT DEFAULT '',
                latitude REAL,
                longitude REAL,
                source TEXT NOT NULL DEFAULT 'web',
                telegram_user_id INTEGER,
                telegram_username TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                admin_note TEXT DEFAULT '',
                estimated_price INTEGER DEFAULT 0,
                client_rating INTEGER,
                client_review TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Default app settings
        defaults = {
            "company_name": "UstaBor Xizmati",
            "company_phone": "+998 71 200 45 45",
            "working_hours": "24/7 — Dam olish kunlarisiz",
            "telegram_bot_token": settings.TELEGRAM_BOT_TOKEN or "",
            "admin_telegram_ids": settings.ADMIN_TELEGRAM_IDS or "",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (k, v),
            )
        if settings.TELEGRAM_BOT_TOKEN:
            conn.execute(
                "UPDATE app_settings SET value = ? WHERE key = 'telegram_bot_token' AND value = ''",
                (settings.TELEGRAM_BOT_TOKEN,),
            )
        if settings.ADMIN_TELEGRAM_IDS:
            conn.execute(
                "UPDATE app_settings SET value = ? WHERE key = 'admin_telegram_ids' AND value = ''",
                (settings.ADMIN_TELEGRAM_IDS,),
            )

        # Default admin account
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing_admin = conn.execute(
            "SELECT id FROM admins WHERE username = ?", (settings.ADMIN_USERNAME,)
        ).fetchone()
        if not existing_admin:
            conn.execute(
                "INSERT INTO admins (username, full_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (
                    settings.ADMIN_USERNAME,
                    "Bosh Administrator",
                    hash_password(settings.ADMIN_PASSWORD),
                    now,
                ),
            )

        # Seed demo client if empty
        if conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
            conn.execute(
                """
                INSERT INTO clients (full_name, phone, password_hash, default_address, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "Sardorbek Alimov",
                    "+998901234567",
                    hash_password("client123"),
                    "Toshkent sh., Chilonzor tumani, 9-kvartal, 14-uy",
                    now,
                ),
            )

        # Seed 30 services if empty
        if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            seed_services = _get_seed_services()
            for idx, svc in enumerate(seed_services, start=1):
                conn.execute(
                    """
                    INSERT INTO services (
                        slug, name, group_name, description, price_from, unit,
                        eta_minutes, image_url, icon, is_popular, is_active, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        svc["slug"],
                        svc["name"],
                        svc["group_name"],
                        svc["description"],
                        svc["price_from"],
                        svc["unit"],
                        svc["eta_minutes"],
                        f"/static/images/services/{svc['slug']}.png",
                        svc["icon"],
                        svc["is_popular"],
                        idx,
                    ),
                )

        # Seed masters if empty
        if conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0] == 0:
            seed_masters = [
                ("Azizbek Karimov", "+998903331122", "Avto va Elektromobil diagnostikasi", "Avto va Transport", 9, 4.95, 312, "Chilonzor, Yakkasaroy", "available"),
                ("Rustam Xolmatov", "+998915552233", "Santexnika va isitish tizimlari", "Muhandislik va Kommunikatsiya", 11, 4.92, 428, "Barcha tumanlar", "available"),
                ("Dilshod Tursunov", "+998937774455", "Elektrik va Wi-Fi tarmoqlari", "Muhandislik va Kommunikatsiya", 8, 4.90, 275, "Yunusobod, Mirzo Ulug'bek", "available"),
                ("Bahrom Niyozov", "+998946668899", "Evro remont, Kafel va G'isht urish", "Qurilish va Ta'mirlash", 14, 4.97, 190, "Barcha tumanlar", "available"),
                ("Javohir Abdullayev", "+998971112244", "Kompyuter, Telefon va TV ta'miri", "Texnika va Elektronika", 7, 4.88, 540, "Shayxontohur, Olmazor", "available"),
                ("Otabek Qodirov", "+998998887766", "Konditsioner va Maishiy texnika", "Texnika va Elektronika", 10, 4.94, 389, "Barcha tumanlar", "busy"),
                ("Umarbek Soliyev", "+998909990011", "Mebel, Deraza-rom va Yog'och o'ymakorlik", "Mebel, Yog'och va Tashqi ishlar", 15, 4.98, 210, "Barcha tumanlar", "available"),
                ("Farhod Rahimov", "+998934445566", "Tom yopish, Mangal va Payvandlash", "Qurilish va Ta'mirlash", 12, 4.91, 164, "Sergeli, Bektemir, Yashnobod", "available"),
                ("Shuhrat Mamatov", "+998952223344", "Yuk mashinalari motor va xodovoy", "Avto va Transport", 13, 4.93, 245, "Sergeli, Toshkent viloyati", "available"),
            ]
            for m in seed_masters:
                conn.execute(
                    """
                    INSERT INTO masters (
                        full_name, phone, specialty, group_name, experience_years,
                        rating, completed_jobs, district, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*m, now),
                )

        # Seed realistic sample orders if empty so Admin & Client panels feel alive immediately
        if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            svc_rows = {r["slug"]: r for r in conn.execute("SELECT id, slug, name FROM services").fetchall()}
            sample_orders = [
                (
                    "UST-1001",
                    svc_rows["santexnik"]["id"],
                    svc_rows["santexnik"]["name"],
                    2,
                    1,
                    "Sardorbek Alimov",
                    "+998901234567",
                    "Chilonzor",
                    "9-kvartal, 14-uy, 28-xonadon",
                    "Oshxona rakovinasi ostidan suv tomchilayapti, smesitel almashtirish kerak.",
                    "Bugun, 14:00 - 16:00",
                    "web",
                    "accepted",
                    "Usta Rustam biriktirildi",
                    120000,
                ),
                (
                    "UST-1002",
                    svc_rows["konditsioner"]["id"],
                    svc_rows["konditsioner"]["name"],
                    6,
                    None,
                    "Malika Karimova",
                    "+998935554411",
                    "Yunusobod",
                    "11-mavze, 42-uy",
                    "Konditsioner yaxshi sovutmayapti, freon quyish va tozalash kerak.",
                    "Tezda",
                    "telegram",
                    "new",
                    "",
                    180000,
                ),
                (
                    "UST-1003",
                    svc_rows["elektromobil"]["id"],
                    svc_rows["elektromobil"]["name"],
                    1,
                    None,
                    "Jamshid Raxmatov",
                    "+998974443322",
                    "Mirzo Ulug'bek",
                    "Buyuk Ipak Yo'li ko'chasi, 105",
                    "BYD Song Plus zaryadka porti xatolik beryapti, kompyuter diagnostika kerak.",
                    "Ertaga 10:00",
                    "telegram",
                    "on_the_way",
                    "Diagnostika uskunasi bilan yo'lga chiqildi",
                    250000,
                ),
                (
                    "UST-1004",
                    svc_rows["evro-remont"]["id"],
                    svc_rows["evro-remont"]["name"],
                    4,
                    1,
                    "Sardorbek Alimov",
                    "+998901234567",
                    "Chilonzor",
                    "9-kvartal, 14-uy, 28-xonadon",
                    "Mehmonxona shiftini gipsokarton va bo'yoq qilish bo'yicha smeta kerak.",
                    "Dam olish kuni",
                    "web",
                    "completed",
                    "Smeta tuzildi va ish muvaffaqiyatli yakunlandi",
                    4500000,
                ),
            ]
            for o in sample_orders:
                conn.execute(
                    """
                    INSERT INTO orders (
                        order_code, service_id, service_name, master_id, client_id,
                        client_name, client_phone, district, address, description,
                        preferred_time, source, status, admin_note, estimated_price,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*o, now, now),
                )


def _get_seed_services() -> List[Dict[str, Any]]:
    return [
        {
            "slug": "avto-ustalari",
            "name": "Avto mashina ustalari",
            "group_name": "Avto va Transport",
            "description": "Dvigatel, xodovoy, kompyuter diagnostika, moy almashtirish va joyida tez yordam.",
            "price_from": 100000,
            "unit": "so'mdan",
            "eta_minutes": 35,
            "icon": "car",
            "is_popular": 1,
        },
        {
            "slug": "elektromobil",
            "name": "Elektromobil ustasi",
            "group_name": "Avto va Transport",
            "description": "BYD, Zeekr, Tesla va boshqa elektromobillar batareya, invertor va dasturiy diagnostikasi.",
            "price_from": 180000,
            "unit": "so'mdan",
            "eta_minutes": 45,
            "icon": "zap",
            "is_popular": 1,
        },
        {
            "slug": "yuk-mashinalar",
            "name": "Yuk mashinalar bo'yicha ustalar",
            "group_name": "Avto va Transport",
            "description": "HOWO, MAN, Kamaz, Isuzu va furalar motor, pnevmo tizim va elektr ta'miri.",
            "price_from": 250000,
            "unit": "so'mdan",
            "eta_minutes": 60,
            "icon": "truck",
            "is_popular": 0,
        },
        {
            "slug": "uy-quruvchi",
            "name": "Uy quruvchi ustalar",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Noldan kalit topshirishgacha uy, hovli, kottej va qo'shimcha binolar qurish.",
            "price_from": 500000,
            "unit": "kelishuv asosida",
            "eta_minutes": 90,
            "icon": "home",
            "is_popular": 1,
        },
        {
            "slug": "evro-remont",
            "name": "Evro remont",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Zamonaviy dizayn asosida kvartira va uylarni sifatli ta'mirlash, shpaklyovka, oboy, tyaga.",
            "price_from": 150000,
            "unit": "m² dan",
            "eta_minutes": 60,
            "icon": "paintbrush",
            "is_popular": 1,
        },
        {
            "slug": "tom-yopish",
            "name": "Tom yopish",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Profnastil, metallocherepitsa, shifer va yumshoq tom yopish hamda gidroizolyatsiya.",
            "price_from": 85000,
            "unit": "m² dan",
            "eta_minutes": 90,
            "icon": "warehouse",
            "is_popular": 0,
        },
        {
            "slug": "gisht-urish",
            "name": "G'isht urish",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Pishgan g'isht, xom g'isht, gazoblok va shlakoblokdan devor va to'siqlar terish.",
            "price_from": 70000,
            "unit": "m² dan",
            "eta_minutes": 90,
            "icon": "blocks",
            "is_popular": 0,
        },
        {
            "slug": "kafelchi",
            "name": "Kafelchi ustalar",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Hammom, oshxona, pol va fasadga kafel, keramogranit va mozaika yotqizish.",
            "price_from": 90000,
            "unit": "m² dan",
            "eta_minutes": 60,
            "icon": "grid",
            "is_popular": 1,
        },
        {
            "slug": "suvoq-boyoq",
            "name": "Suvoq va bo'yoqchilik (Malyar)",
            "group_name": "Qurilish va Ta'mirlash",
            "description": "Qum-sement suvoq, gips shpaklyovka, dekorativ travertin va devor bo'yash ishlari.",
            "price_from": 45000,
            "unit": "m² dan",
            "eta_minutes": 60,
            "icon": "paint-roller",
            "is_popular": 0,
        },
        {
            "slug": "santexnik",
            "name": "Santexnik usta",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Quvur almashtirish, smesitel, unitaz, dush kabina o'rnatish va tiqilgan trubalarni ochish.",
            "price_from": 80000,
            "unit": "so'mdan",
            "eta_minutes": 30,
            "icon": "droplets",
            "is_popular": 1,
        },
        {
            "slug": "elektrik",
            "name": "Elektrik ustalar",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Sim tortish, shit yig'ish, rozetka, lyustra o'rnatish va qisqa tutashuvlarni bartaraf etish.",
            "price_from": 80000,
            "unit": "so'mdan",
            "eta_minutes": 30,
            "icon": "lightbulb",
            "is_popular": 1,
        },
        {
            "slug": "konditsioner",
            "name": "Konditsioner ustasi",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Konditsioner o'rnatish, yechish, freon quyish, chuqur tozalash va plata ta'mirlash.",
            "price_from": 120000,
            "unit": "so'mdan",
            "eta_minutes": 40,
            "icon": "wind",
            "is_popular": 1,
        },
        {
            "slug": "wifi-ornatish",
            "name": "Wi-Fi o'rnatish xizmati",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Router sozlash, Mesh tizim o'rnatish, kabel tortish va uyda kuchli internet qamrovi.",
            "price_from": 70000,
            "unit": "so'mdan",
            "eta_minutes": 40,
            "icon": "wifi",
            "is_popular": 0,
        },
        {
            "slug": "issiq-pol",
            "name": "Issiq pol va isitish (Kotyol)",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Ikki konturli kotyol o'rnatish, issiq pol montaji, radiator yuvish va sozlash.",
            "price_from": 150000,
            "unit": "so'mdan",
            "eta_minutes": 50,
            "icon": "flame",
            "is_popular": 0,
        },
        {
            "slug": "video-kuzatuv",
            "name": "Video kuzatuv kameralari o'rnatish",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Uy va ofis uchun IP/HD kameralar o'rnatish, telefonga ulash va yozuv sozlash.",
            "price_from": 140000,
            "unit": "kamera boshiga",
            "eta_minutes": 55,
            "icon": "cctv",
            "is_popular": 0,
        },
        {
            "slug": "quyosh-panellari",
            "name": "Quyosh panellari o'rnatish",
            "group_name": "Muhandislik va Kommunikatsiya",
            "description": "Uy va biznes uchun quyosh elektr stansiyalari, gibrid invertor va akkumulyator montaji.",
            "price_from": 400000,
            "unit": "kelishuv asosida",
            "eta_minutes": 120,
            "icon": "sun",
            "is_popular": 0,
        },
        {
            "slug": "kompyuter-ustasi",
            "name": "Kompyuter ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "Noutbuk va PK ta'miri, Windows o'rnatish, termopasta almashtirish, viruslardan tozalash.",
            "price_from": 70000,
            "unit": "so'mdan",
            "eta_minutes": 40,
            "icon": "laptop",
            "is_popular": 1,
        },
        {
            "slug": "telefon-ustasi",
            "name": "Telefon ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "iPhone va Android ekran, batareya, zaryad uyasi almashtirish va dasturiy tiklash.",
            "price_from": 80000,
            "unit": "so'mdan",
            "eta_minutes": 35,
            "icon": "smartphone",
            "is_popular": 1,
        },
        {
            "slug": "televizor-ustasi",
            "name": "Televizor ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "Smart TV, LED/OLED televizorlar podsvetka, blok pitaniya va matritsa ta'miri.",
            "price_from": 110000,
            "unit": "so'mdan",
            "eta_minutes": 45,
            "icon": "tv",
            "is_popular": 0,
        },
        {
            "slug": "soat-ustasi",
            "name": "Soat ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "Mexanik, kvarts va smart soatlar ta'miri, batareya almashtirish, tozalash va sozlash.",
            "price_from": 40000,
            "unit": "so'mdan",
            "eta_minutes": 45,
            "icon": "watch",
            "is_popular": 0,
        },
        {
            "slug": "maishiy-texnika",
            "name": "Maishiy texnikalar ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "Kir yuvish mashinasi, muzlatkich, idish yuvish mashinasi, changyutgich va pech ta'miri.",
            "price_from": 90000,
            "unit": "so'mdan",
            "eta_minutes": 40,
            "icon": "refrigerator",
            "is_popular": 1,
        },
        {
            "slug": "gaz-plita",
            "name": "Gaz plita va duxovka ustasi",
            "group_name": "Texnika va Elektronika",
            "description": "Gaz plita, vtyajka va elektr duxovkalarni ta'mirlash, forsunka va sizib chiqishni tekshirish.",
            "price_from": 80000,
            "unit": "so'mdan",
            "eta_minutes": 40,
            "icon": "flame",
            "is_popular": 0,
        },
        {
            "slug": "mebelchi",
            "name": "Mebelchi usta",
            "group_name": "Mebel, Yog'och va Tashqi ishlar",
            "description": "Oshxona, shkaf-kupe, yotoqxona mebellarini yasash, yig'ish, ko'chirish va ta'mirlash.",
            "price_from": 120000,
            "unit": "so'mdan",
            "eta_minutes": 50,
            "icon": "armchair",
            "is_popular": 1,
        },
        {
            "slug": "deraza-rom-eshik",
            "name": "Deraza rom eshik ustasi",
            "group_name": "Mebel, Yog'och va Tashqi ishlar",
            "description": "Akfa/Plastik va alyumin romlar, MDF va temir eshiklar o'rnatish, regulirovka va rezinka almashtirish.",
            "price_from": 85000,
            "unit": "so'mdan",
            "eta_minutes": 45,
            "icon": "door-open",
            "is_popular": 1,
        },
        {
            "slug": "yogoch-oymakorlik",
            "name": "Yog'och o'ymakorlik ustasi",
            "group_name": "Mebel, Yog'och va Tashqi ishlar",
            "description": "Milliy naqshli darvoza, eshik, ustun, xontaxta va dekorativ panellar o'ymakorligi.",
            "price_from": 250000,
            "unit": "kelishuv asosida",
            "eta_minutes": 90,
            "icon": "trees",
            "is_popular": 0,
        },
        {
            "slug": "mangal-quruvchi",
            "name": "Mangal quruvchi ustasi",
            "group_name": "Mebel, Yog'och va Tashqi ishlar",
            "description": "Hovli va choyxona uchun olovbardosh g'ishtdan mangal, tandir, o'choq va kamin qurish.",
            "price_from": 600000,
            "unit": "kelishuv asosida",
            "eta_minutes": 90,
            "icon": "flame-kindling",
            "is_popular": 0,
        },
        {
            "slug": "payvandlash",
            "name": "Payvandlash (Svarka) ustasi",
            "group_name": "Mebel, Yog'och va Tashqi ishlar",
            "description": "Naves, panjara, darvoza, zinapoya va metall konstruksiyalarni payvandlash va mustahkamlash.",
            "price_from": 120000,
            "unit": "so'mdan",
            "eta_minutes": 50,
            "icon": "sparkles",
            "is_popular": 0,
        },
        {
            "slug": "bogbon-landshaft",
            "name": "Bog'bon va landshaft dizayni",
            "group_name": "Uy xizmatlari va Boshqalar",
            "description": "Gazon ekish, daraxtlarni butash, avtomatik sug'orish tizimi va hovlini ko'kalamzorlashtirish.",
            "price_from": 150000,
            "unit": "so'mdan",
            "eta_minutes": 75,
            "icon": "flower-2",
            "is_popular": 0,
        },
        {
            "slug": "qulf-ochish",
            "name": "Qulf ochish va kalit yasash",
            "group_name": "Uy xizmatlari va Boshqalar",
            "description": "Qulflangan uy, seyf va mashina eshiklarini zararsiz ochish, zamonaviy qulflar o'rnatish.",
            "price_from": 90000,
            "unit": "so'mdan",
            "eta_minutes": 25,
            "icon": "key-round",
            "is_popular": 0,
        },
        {
            "slug": "klining-dezinfeksiya",
            "name": "Umumiy tozalash va dezinfeksiya",
            "group_name": "Uy xizmatlari va Boshqalar",
            "description": "Ta'mirdan keyingi tozalash, mebel ximchistkasi va hasharotlarga qarshi dezinfeksiya.",
            "price_from": 180000,
            "unit": "so'mdan",
            "eta_minutes": 60,
            "icon": "spray-can",
            "is_popular": 0,
        },
    ]


# --- Repository Helpers ---

def get_setting(key: str, default: str = "") -> str:
    with db_session() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def get_all_settings() -> Dict[str, str]:
    with db_session() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def set_setting(key: str, value: str) -> None:
    with db_session() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def list_services(active_only: bool = True, group_name: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM services WHERE 1=1"
    params: List[Any] = []
    if active_only:
        query += " AND is_active = 1"
    if group_name and group_name != "Barchasi":
        query += " AND group_name = ?"
        params.append(group_name)
    if search:
        query += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(group_name) LIKE ?)"
        s = f"%{search.strip().lower()}%"
        params.extend([s, s, s])
    query += " ORDER BY sort_order ASC, id ASC"
    with db_session() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def list_service_groups(active_only: bool = True) -> List[str]:
    query = "SELECT DISTINCT group_name FROM services"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY MIN(sort_order) ASC"
    with db_session() as conn:
        # SQLite needs GROUP BY for MIN(sort_order)
        q = (
            "SELECT group_name FROM services "
            + ("WHERE is_active = 1 " if active_only else "")
            + "GROUP BY group_name ORDER BY MIN(sort_order) ASC"
        )
        return [r["group_name"] for r in conn.execute(q).fetchall()]


def get_service(service_id: int) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        return dict(row) if row else None


def create_order(
    *,
    service_id: Optional[int],
    service_name: str,
    client_name: str,
    client_phone: str,
    address: str,
    district: str = "",
    description: str = "",
    preferred_time: str = "Tezda",
    photo_path: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    source: str = "web",
    client_id: Optional[int] = None,
    telegram_user_id: Optional[int] = None,
    telegram_username: str = "",
) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        # Link existing client by phone if client_id not given
        if not client_id and client_phone:
            c_row = conn.execute("SELECT id FROM clients WHERE phone = ?", (client_phone.strip(),)).fetchone()
            if c_row:
                client_id = c_row["id"]

        last_row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM orders").fetchone()
        next_num = 1001 + int(last_row["max_id"])
        order_code = f"UST-{next_num}"

        estimated_price = 0
        if service_id:
            s_row = conn.execute("SELECT price_from FROM services WHERE id = ?", (service_id,)).fetchone()
            if s_row:
                estimated_price = s_row["price_from"]

        cur = conn.execute(
            """
            INSERT INTO orders (
                order_code, service_id, service_name, client_id,
                client_name, client_phone, district, address, description,
                preferred_time, photo_path, latitude, longitude,
                source, telegram_user_id, telegram_username,
                status, estimated_price, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
            """,
            (
                order_code,
                service_id,
                service_name,
                client_id,
                client_name.strip(),
                client_phone.strip(),
                district.strip(),
                address.strip(),
                description.strip(),
                preferred_time.strip() or "Tezda",
                photo_path,
                latitude,
                longitude,
                source,
                telegram_user_id,
                telegram_username or "",
                estimated_price,
                now,
                now,
            ),
        )
        order_id = cur.lastrowid
        row = conn.execute(
            """
            SELECT o.*, m.full_name AS master_name, m.phone AS master_phone
            FROM orders o
            LEFT JOIN masters m ON m.id = o.master_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
        return dict(row)


def list_orders(
    *,
    status: Optional[str] = None,
    service_id: Optional[int] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    client_phone: Optional[str] = None,
    client_id: Optional[int] = None,
    telegram_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query = """
        SELECT o.*, m.full_name AS master_name, m.phone AS master_phone,
               s.image_url AS service_image, s.group_name AS service_group
        FROM orders o
        LEFT JOIN masters m ON m.id = o.master_id
        LEFT JOIN services s ON s.id = o.service_id
        WHERE 1=1
    """
    params: List[Any] = []
    if status and status != "all":
        query += " AND o.status = ?"
        params.append(status)
    if service_id:
        query += " AND o.service_id = ?"
        params.append(service_id)
    if source and source != "all":
        query += " AND o.source = ?"
        params.append(source)
    if client_phone and client_id:
        query += " AND (o.client_id = ? OR o.client_phone = ?)"
        params.extend([client_id, client_phone.strip()])
    elif client_phone:
        query += " AND o.client_phone = ?"
        params.append(client_phone.strip())
    elif client_id:
        query += " AND o.client_id = ?"
        params.append(client_id)
    if telegram_user_id:
        query += " AND o.telegram_user_id = ?"
        params.append(telegram_user_id)
    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(o.order_code) LIKE ? OR LOWER(o.client_name) LIKE ? OR LOWER(o.client_phone) LIKE ? OR LOWER(o.service_name) LIKE ? OR LOWER(o.address) LIKE ?)"
        params.extend([s, s, s, s, s])
    query += " ORDER BY o.id DESC"
    with db_session() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT o.*, m.full_name AS master_name, m.phone AS master_phone,
                   s.image_url AS service_image, s.group_name AS service_group
            FROM orders o
            LEFT JOIN masters m ON m.id = o.master_id
            LEFT JOIN services s ON s.id = o.service_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
        return dict(row) if row else None


def update_order(
    order_id: int,
    *,
    status: Optional[str] = None,
    master_id: Optional[int] = None,
    clear_master: bool = False,
    admin_note: Optional[str] = None,
    estimated_price: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = ["updated_at = ?"]
    params: List[Any] = [now]
    if status is not None and status in STATUS_LABELS:
        fields.append("status = ?")
        params.append(status)
    if clear_master:
        fields.append("master_id = NULL")
    elif master_id is not None:
        fields.append("master_id = ?")
        params.append(master_id)
    if admin_note is not None:
        fields.append("admin_note = ?")
        params.append(admin_note)
    if estimated_price is not None:
        fields.append("estimated_price = ?")
        params.append(estimated_price)

    params.append(order_id)
    with db_session() as conn:
        conn.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", params)
    return get_order(order_id)


def list_masters() -> List[Dict[str, Any]]:
    with db_session() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM masters ORDER BY id ASC").fetchall()]


def get_dashboard_stats() -> Dict[str, Any]:
    with db_session() as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'new'").fetchone()[0]
        active_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status IN ('accepted', 'on_the_way', 'in_progress')"
        ).fetchone()[0]
        completed_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'").fetchone()[0]
        web_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'web'").fetchone()[0]
        tg_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'telegram'").fetchone()[0]
        total_services = conn.execute("SELECT COUNT(*) FROM services WHERE is_active = 1").fetchone()[0]
        total_masters = conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0]
        by_service = [
            dict(r)
            for r in conn.execute(
                """
                SELECT service_name, COUNT(*) AS total,
                       SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) AS new_count
                FROM orders
                GROUP BY service_name
                ORDER BY total DESC, new_count DESC
                LIMIT 10
                """
            ).fetchall()
        ]
        return {
            "total_orders": total_orders,
            "new_orders": new_orders,
            "active_orders": active_orders,
            "completed_orders": completed_orders,
            "web_orders": web_orders,
            "tg_orders": tg_orders,
            "total_services": total_services,
            "total_masters": total_masters,
            "by_service": by_service,
        }
