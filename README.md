# UstaBor — Sayt va Telegram Bot orqali Usta Chaqirish Xizmati

Ushbu dastur **Veb-sayt (Mijoz va Admin panellari)** hamda **Telegram Bot** orqali yagona SQLite ma'lumotlar bazasida ishlaydigan professional usta chaqirish tizimidir.

## Asosiy imkoniyatlar
- **30 ta xizmat yo'nalishi (rasmlari bilan):**
  - Avto mashina ustalari, Elektromobil ustasi, Yuk mashinalar ustalari
  - Uy quruvchi ustalar, Evro remont, Tom yopish, G'isht urish, Kafelchi ustalar, Suvoq va bo'yoqchilik
  - Santexnik usta, Elektrik ustalar, Konditsioner ustasi, Wi-Fi o'rnatish, Issiq pol/Kotyol, Video kuzatuv, Quyosh panellari
  - Kompyuter ustasi, Telefon ustasi, Televizor ustasi, Soat ustasi, Maishiy texnikalar ustasi, Gaz plita ustasi
  - Mebelchi usta, Deraza rom eshik ustasi, Yog'och o'ymakorlik, Mangal quruvchi, Payvandlash (Svarka)
  - Bog'bon va landshaft dizayni, Qulf ochish va kalit yasash, Umumiy tozalash va dezinfeksiya
- **Alohida Mijoz paneli (`/` va `/client`):**
  - Xizmatlarni qidirish, yo'nalish bo'yicha saralash, rasm biriktirib tezkor ariza yuborish
  - Telefon raqam yoki shaxsiy kabinet orqali sayt va Telegram botdan berilgan arizalar holatini kuzatish, ustani baholash
- **Alohida Admin paneli (`/admin`):**
  - Xizmatlar bo'yicha kelib tushgan arizalar statistikasi va jonli ro'yxati (`Sayt` va `Telegram Bot` manbasi bilan)
  - Ustani biriktirish, ariza holatini o'zgartirish (mijozga Telegramdan avtomatik xabar boradi)
  - Xizmatlar va ustalarni qo'shish/tahrirlash
  - Telegram Bot tokeni va Admin ID larini panelning o'zidan kiritib ishga tushirish
- **Telegram Bot (`aiogram` v3):**
  - Xizmatlar katalogi rasmlari bilan, bosqichma-bosqich ariza qoldirish (telefon, lokatsiya, muammo rasmi), "Mening arizalarim" va Telegram ichidan Admin boshqaruvi.

## Ishga tushirish
1. Virtual muhitni faollashtirib serverni ishga tushiring:
   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```
2. Brauzerda oching:
   - **Mijoz sayti:** `http://127.0.0.1:5002/`
   - **Mijoz paneli (Kabinet):** `http://127.0.0.1:5003/` (Demo: `+998901234567` / `client123`)
   - **Admin paneli:** `http://127.0.0.1:5004/` (Standart: `admin` / `admin123`)

## Telegram Botni ulash
1. Telegramda `@BotFather` ga kirib `/newbot` orqali yangi bot yarating va **Token** oling.
2. Admin paneldagi **Telegram Bot** bo'limiga tokenni kiriting va **Saqlash va Botni ishga tushirish** tugmasini bosing (yoki `.env` fayliga `TELEGRAM_BOT_TOKEN=...` yozing).
3. Yangi arizalar Telegramingizga ham kelishi uchun botingizga `/id` buyrug'ini yuboring va olingan raqamni **Admin Telegram ID lari** maydoniga kiriting.

## Vercel orqali Deploy qilish
Loyihada [vercel.json](vercel.json) va [api/index.py](api/index.py) tayyorlangan:
1. GitHub repozitoriyasini Vercel'ga ulang (`Import Git Repository`).
2. **Environment Variables** bo'limiga quyidagilarni kiriting:
   - `TELEGRAM_BOT_TOKEN` — `@BotFather` tokeni
   - `ADMIN_USERNAME` — masalan `admin`
   - `ADMIN_PASSWORD` — kuchli admin paroli
   - `SECRET_KEY` — tasodifiy maxfiy kalit
   - `ADMIN_TELEGRAM_IDS` — admin Telegram ID lari
3. Deploy tugagach, saytdagi `/admin` paneliga kirib **Telegram Bot → Saqlash va Botni ishga tushirish** tugmasini bosing — bot avtomatik ravishda Vercel Webhook (`https://<sizning-domen>/api/telegram/webhook`) rejimiga ulanadi.

> **Eslatma:** Vercel serverless muhitida fayl tizimi vaqtinchalik (`/tmp/usta_xizmati.db`), doimiy ma'lumotlar uchun keyinchalik PostgreSQL/Turso bazasiga ulash tavsiya etiladi.
