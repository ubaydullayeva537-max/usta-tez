import logging
import secrets
from pathlib import Path
from typing import List, Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.auth import normalize_phone
from app.config import IS_VERCEL, SERVICES_IMG_DIR, UPLOADS_DIR
from app.database import (
    STATUS_LABELS,
    create_order,
    get_all_settings,
    get_order,
    get_service,
    list_orders,
    list_service_groups,
    list_services,
    update_order,
)

logger = logging.getLogger("ustabor.bot")
router = Router()


class OrderForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_address = State()
    waiting_description = State()
    waiting_photo = State()
    waiting_time = State()
    confirm = State()


def _admin_ids() -> List[int]:
    raw = get_all_settings().get("admin_telegram_ids", "")
    ids: List[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


def _is_tg_admin(user_id: Optional[int]) -> bool:
    return bool(user_id and user_id in _admin_ids())


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🛠 Xizmatlar katalogi"), KeyboardButton(text="⚡ Tezkor usta chaqirish")],
        [KeyboardButton(text="📋 Mening arizalarim"), KeyboardButton(text="📞 Aloqa va Ish vaqti")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🔐 Admin: Yangi arizalar")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def _format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


def _status_emoji(status: str) -> str:
    return {
        "new": "🆕",
        "accepted": "✅",
        "on_the_way": "🚗",
        "in_progress": "🔧",
        "completed": "🏁",
        "cancelled": "❌",
    }.get(status, "📌")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    cfg = get_all_settings()
    company_name = cfg.get("company_name", "UstaBor Xizmati")
    is_admin = _is_tg_admin(message.from_user.id if message.from_user else None)

    welcome = (
        f"👋 Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"<b>{company_name}</b> rasmiy Telegram botiga xush kelibsiz.\n"
        f"Bu yerda 30+ yo'nalishdagi malakali ustalarni 1 daqiqada chaqirishingiz mumkin:\n\n"
        f"• Avto, Elektromobil va Yuk mashina ustalari\n"
        f"• Uy qurish, Evro remont, Kafel, G'isht, Tom yopish\n"
        f"• Santexnik, Elektrik, Konditsioner, Wi-Fi\n"
        f"• Kompyuter, Telefon, TV, Soat, Maishiy texnika\n"
        f"• Mebel, Rom-eshik, Mangal, Yog'och o'ymakorlik va boshqalar!\n\n"
        f"Quyidagi tugmalardan birini tanlang 👇"
    )
    await message.answer(welcome, reply_markup=main_menu_kb(is_admin=is_admin))


@router.message(Command("id"))
async def cmd_my_id(message: Message) -> None:
    uid = message.from_user.id if message.from_user else "Noma'lum"
    await message.answer(
        f"🆔 Sizning Telegram ID raqamingiz: <code>{uid}</code>\n"
        f"Admin bildirishnomalarini olish uchun ushbu ID ni veb Admin Paneldagi Telegram Bot sozlamalariga kiriting."
    )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_any(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_admin = _is_tg_admin(message.from_user.id if message.from_user else None)
    await message.answer("Amal bekor qilindi. Bosh menyudasiz.", reply_markup=main_menu_kb(is_admin=is_admin))


@router.message(F.text == "🛠 Xizmatlar katalogi")
async def show_groups(message: Message) -> None:
    groups = list_service_groups(active_only=True)
    builder = InlineKeyboardBuilder()
    for idx, grp in enumerate(groups):
        builder.button(text=f"📂 {grp}", callback_data=f"grp:{idx}")
    builder.adjust(1)
    await message.answer(
        "<b>Xizmat yo'nalishini tanlang:</b>\nHar bir yo'nalish ichida kerakli usta turini ko'rasiz.",
        reply_markup=builder.as_markup(),
    )


@router.message(F.text == "⚡ Tezkor usta chaqirish")
async def show_popular_services(message: Message) -> None:
    services = [s for s in list_services(active_only=True) if s["is_popular"]][:12]
    if not services:
        services = list_services(active_only=True)[:12]
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"🔧 {s['name']}", callback_data=f"svc:{s['id']}")
    builder.adjust(2)
    await message.answer(
        "<b>Eng ko'p chaqiriladigan ustalar:</b>\nKerakli xizmatni bosing 👇",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "back_groups")
async def cb_back_groups(callback: CallbackQuery) -> None:
    groups = list_service_groups(active_only=True)
    builder = InlineKeyboardBuilder()
    for idx, grp in enumerate(groups):
        builder.button(text=f"📂 {grp}", callback_data=f"grp:{idx}")
    builder.adjust(1)
    await callback.message.answer("<b>Xizmat yo'nalishini tanlang:</b>", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("grp:"))
async def cb_group_services(callback: CallbackQuery) -> None:
    idx = int(callback.data.split(":", 1)[1])
    groups = list_service_groups(active_only=True)
    if idx < 0 or idx >= len(groups):
        await callback.answer("Yo'nalish topilmadi", show_alert=True)
        return
    group_name = groups[idx]
    services = list_services(active_only=True, group_name=group_name)
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"🛠 {s['name']} ({_format_price(s['price_from'])})", callback_data=f"svc:{s['id']}")
    builder.button(text="⬅️ Yo'nalishlarga qaytish", callback_data="back_groups")
    builder.adjust(1)
    await callback.message.answer(
        f"📂 <b>{group_name}</b>\nKerakli xizmatni tanlang:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:"))
async def cb_service_detail(callback: CallbackQuery) -> None:
    service_id = int(callback.data.split(":", 1)[1])
    svc = get_service(service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi", show_alert=True)
        return

    caption = (
        f"🛠 <b>{svc['name']}</b>\n"
        f"📂 Yo'nalish: <i>{svc['group_name']}</i>\n\n"
        f"{svc['description']}\n\n"
        f"💰 Boshlang'ich narx: <b>{_format_price(svc['price_from'])} {svc['unit']}</b>\n"
        f"⏱ O'rtacha yetib kelish: <b>~{svc['eta_minutes']} daqiqa</b>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 Ariza qoldirish (Usta chaqirish)", callback_data=f"order:{svc['id']}")],
            [InlineKeyboardButton(text="⬅️ Boshqa xizmatlar", callback_data="back_groups")],
        ]
    )

    img_filename = Path(svc["image_url"]).name
    img_path = SERVICES_IMG_DIR / img_filename
    if img_path.exists():
        await callback.message.answer_photo(photo=FSInputFile(str(img_path)), caption=caption, reply_markup=kb)
    else:
        await callback.message.answer(caption, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("order:"))
async def cb_start_order(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":", 1)[1])
    svc = get_service(service_id)
    if not svc:
        await callback.answer("Xizmat topilmadi", show_alert=True)
        return

    await state.clear()
    await state.update_data(service_id=svc["id"], service_name=svc["name"])
    await state.set_state(OrderForm.waiting_name)

    tg_name = callback.from_user.full_name if callback.from_user else ""
    rows = []
    if tg_name:
        rows.append([KeyboardButton(text=tg_name)])
    rows.append([KeyboardButton(text="❌ Bekor qilish")])

    await callback.message.answer(
        f"📝 <b>{svc['name']}</b> bo'yicha ariza rasmiylashtirish.\n\n"
        f"1/6. Ism-familiyangizni kiriting (yoki tugmani bosing):",
        reply_markup=ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True),
    )
    await callback.answer()


@router.message(OrderForm.waiting_name)
async def step_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Iltimos, to'liq ismingizni kiriting:")
        return
    await state.update_data(client_name=name)
    await state.set_state(OrderForm.waiting_phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "2/6. Telefon raqamingizni yuboring (pastdagi tugmani bosing yoki +998901234567 shaklida yozing):",
        reply_markup=kb,
    )


@router.message(OrderForm.waiting_phone)
async def step_phone(message: Message, state: FSMContext) -> None:
    if message.contact and message.contact.phone_number:
        phone = normalize_phone(message.contact.phone_number)
    else:
        phone = normalize_phone(message.text or "")
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 9:
        await message.answer("Telefon raqami noto'g'ri ko'rinadi. Masalan: +998901234567")
        return

    await state.update_data(client_phone=phone)
    await state.set_state(OrderForm.waiting_address)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "3/6. Manzilingizni yozing (tuman, ko'cha, uy) yoki lokatsiya yuboring:",
        reply_markup=kb,
    )


@router.message(OrderForm.waiting_address)
async def step_address(message: Message, state: FSMContext) -> None:
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        await state.update_data(
            address=f"Telegram lokatsiya ({lat:.5f}, {lon:.5f})",
            latitude=lat,
            longitude=lon,
        )
    else:
        addr = (message.text or "").strip()
        if len(addr) < 4:
            await message.answer("Iltimos, to'liqroq manzil kiriting:")
            return
        await state.update_data(address=addr, latitude=None, longitude=None)

    await state.set_state(OrderForm.waiting_description)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Tafsilot shart emas")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "4/6. Muammo yoki ish haqida qisqacha ma'lumot yozing:",
        reply_markup=kb,
    )


@router.message(OrderForm.waiting_description)
async def step_description(message: Message, state: FSMContext) -> None:
    desc = (message.text or "").strip()
    if desc == "⏭ Tafsilot shart emas":
        desc = ""
    await state.update_data(description=desc)
    await state.set_state(OrderForm.waiting_photo)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ Rasm kerak emas")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "5/6. Muammo rasmini yuborishingiz mumkin (ixtiyoriy — admin va usta ko'rishi uchun):",
        reply_markup=kb,
    )


@router.message(OrderForm.waiting_photo)
async def step_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    photo_path = ""
    if message.photo:
        largest = message.photo[-1]
        filename = f"tg_{secrets.token_hex(6)}.jpg"
        dest = UPLOADS_DIR / filename
        await bot.download(largest, destination=dest)
        photo_path = f"/tmp-uploads/{filename}" if IS_VERCEL else f"/static/uploads/{filename}"
    elif message.text != "⏭ Rasm kerak emas":
        await message.answer("Iltimos, rasm yuboring yoki '⏭ Rasm kerak emas' tugmasini bosing.")
        return

    await state.update_data(photo_path=photo_path)
    await state.set_state(OrderForm.waiting_time)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚡ Tezda (1 soat ichida)"), KeyboardButton(text="☀️ Bugun kunduzi")],
            [KeyboardButton(text="🌙 Bugun kechqurun"), KeyboardButton(text="📅 Ertaga")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer("6/6. Usta qachon yetib borishi qulay?", reply_markup=kb)


@router.message(OrderForm.waiting_time)
async def step_time(message: Message, state: FSMContext) -> None:
    preferred_time = (message.text or "Tezda").strip()
    await state.update_data(preferred_time=preferred_time)
    data = await state.get_data()
    await state.set_state(OrderForm.confirm)

    summary = (
        f"📋 <b>Arizangizni tekshiring:</b>\n\n"
        f"🛠 Xizmat: <b>{data['service_name']}</b>\n"
        f"👤 Mijoz: <b>{data['client_name']}</b>\n"
        f"📞 Telefon: <b>{data['client_phone']}</b>\n"
        f"📍 Manzil: <b>{data['address']}</b>\n"
        f"⏰ Vaqt: <b>{preferred_time}</b>\n"
        f"📝 Izoh: <i>{data.get('description') or 'Kiritilmagan'}</i>\n"
        f"🖼 Rasm: {'Biriktirilgan ✅' if data.get('photo_path') else 'Yo‘q'}"
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Arizani tasdiqlash")],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.answer(summary, reply_markup=kb)


@router.message(OrderForm.confirm, F.text == "✅ Arizani tasdiqlash")
async def step_confirm(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order = create_order(
        service_id=data.get("service_id"),
        service_name=data["service_name"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        address=data["address"],
        description=data.get("description", ""),
        preferred_time=data.get("preferred_time", "Tezda"),
        photo_path=data.get("photo_path", ""),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        source="telegram",
        telegram_user_id=message.from_user.id if message.from_user else None,
        telegram_username=(message.from_user.username or "") if message.from_user else "",
    )
    await state.clear()
    is_admin = _is_tg_admin(message.from_user.id if message.from_user else None)

    await message.answer(
        f"🎉 <b>Arizangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"🆔 Ariza raqami: <b>{order['order_code']}</b>\n"
        f"🛠 Xizmat: <b>{order['service_name']}</b>\n"
        f"📊 Holati: <b>{STATUS_LABELS.get(order['status'], order['status'])}</b>\n\n"
        f"Operatorimiz tez orada siz bilan bog'lanadi. Arizangiz holatini "
        f"<b>📋 Mening arizalarim</b> bo'limidan kuzatishingiz mumkin.",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )

    await notify_admins_new_order(bot, order)


@router.message(F.text == "📋 Mening arizalarim")
async def show_my_orders(message: Message) -> None:
    uid = message.from_user.id if message.from_user else None
    orders = list_orders(telegram_user_id=uid)[:10] if uid else []
    if not orders:
        await message.answer(
            "Sizda hali Telegram orqali yuborilgan arizalar yo'q.\n"
            "🛠 Xizmatlar katalogidan kerakli ustani tanlab ariza qoldiring!"
        )
        return

    lines = ["<b>📋 So'nggi arizalaringiz:</b>\n"]
    for o in orders:
        emoji = _status_emoji(o["status"])
        status_uz = STATUS_LABELS.get(o["status"], o["status"])
        master_info = f"\n   👨‍🔧 Usta: {o['master_name']} ({o['master_phone']})" if o.get("master_name") else ""
        lines.append(
            f"{emoji} <b>{o['order_code']}</b> — {o['service_name']}\n"
            f"   Holat: <b>{status_uz}</b> | {o['created_at']}{master_info}\n"
        )
    await message.answer("\n".join(lines))


@router.message(F.text == "📞 Aloqa va Ish vaqti")
async def show_contact(message: Message) -> None:
    cfg = get_all_settings()
    await message.answer(
        f"🏢 <b>{cfg.get('company_name', 'UstaBor Xizmati')}</b>\n\n"
        f"📞 Call-markaz: <b>{cfg.get('company_phone', '+998 71 200 45 45')}</b>\n"
        f"⏰ Ish vaqti: <b>{cfg.get('working_hours', '24/7')}</b>\n"
        f"🌐 Veb-sayt va Admin panel orqali barcha xizmatlar yagona bazada ishlaydi."
    )


@router.message(F.text == "🔐 Admin: Yangi arizalar")
async def admin_recent_orders(message: Message) -> None:
    if not _is_tg_admin(message.from_user.id if message.from_user else None):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    orders = list_orders()[:8]
    if not orders:
        await message.answer("Hozircha arizalar yo'q.")
        return

    for o in orders:
        await message.answer(_format_admin_order_text(o), reply_markup=_admin_order_kb(o["id"], o["status"]))


@router.callback_query(F.data.startswith("adm_st:"))
async def cb_admin_status(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_tg_admin(callback.from_user.id if callback.from_user else None):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    _, order_id_str, new_status = callback.data.split(":", 2)
    order = update_order(int(order_id_str), status=new_status)
    if not order:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            _format_admin_order_text(order),
            reply_markup=_admin_order_kb(order["id"], order["status"]),
        )
    except Exception:
        pass

    await notify_client_status(bot, order)
    await callback.answer(f"Holat o'zgardi: {STATUS_LABELS.get(new_status, new_status)}")


def _format_admin_order_text(o: dict) -> str:
    src = "🤖 Telegram" if o["source"] == "telegram" else "🌐 Sayt"
    emoji = _status_emoji(o["status"])
    return (
        f"📥 <b>Ariza {o['order_code']}</b> ({src})\n"
        f"🛠 Xizmat: <b>{o['service_name']}</b>\n"
        f"👤 Mijoz: <b>{o['client_name']}</b>\n"
        f"📞 Tel: <code>{o['client_phone']}</code>\n"
        f"📍 Manzil: {o['address']}\n"
        f"⏰ Vaqt: {o['preferred_time']}\n"
        f"📝 Izoh: {o['description'] or '—'}\n"
        f"📊 Holat: {emoji} <b>{STATUS_LABELS.get(o['status'], o['status'])}</b>"
    )


def _admin_order_kb(order_id: int, status: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"adm_st:{order_id}:accepted"),
                InlineKeyboardButton(text="🚗 Yo'lda", callback_data=f"adm_st:{order_id}:on_the_way"),
            ],
            [
                InlineKeyboardButton(text="🏁 Bajarildi", callback_data=f"adm_st:{order_id}:completed"),
                InlineKeyboardButton(text="❌ Bekor", callback_data=f"adm_st:{order_id}:cancelled"),
            ],
        ]
    )


async def notify_admins_new_order(bot: Bot, order: dict) -> None:
    admin_ids = _admin_ids()
    if not admin_ids:
        return
    text = "🔔 <b>YANGI ARIZA TUSHDI!</b>\n\n" + _format_admin_order_text(order)
    kb = _admin_order_kb(order["id"], order["status"])
    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=text, reply_markup=kb)
            if order.get("latitude") and order.get("longitude"):
                await bot.send_location(chat_id=aid, latitude=order["latitude"], longitude=order["longitude"])
        except Exception as exc:
            logger.warning("Failed to notify admin %s: %s", aid, exc)


async def notify_client_status(bot: Bot, order: dict) -> None:
    tg_uid = order.get("telegram_user_id")
    if not tg_uid:
        return
    emoji = _status_emoji(order["status"])
    status_uz = STATUS_LABELS.get(order["status"], order["status"])
    master_line = (
        f"\n👨‍🔧 Biriktirilgan usta: <b>{order['master_name']}</b> ({order['master_phone']})"
        if order.get("master_name")
        else ""
    )
    note_line = f"\n💬 Admin izohi: {order['admin_note']}" if order.get("admin_note") else ""
    try:
        await bot.send_message(
            chat_id=tg_uid,
            text=(
                f"{emoji} <b>Arizangiz holati yangilandi!</b>\n\n"
                f"🆔 Ariza: <b>{order['order_code']}</b>\n"
                f"🛠 Xizmat: <b>{order['service_name']}</b>\n"
                f"📊 Yangi holat: <b>{status_uz}</b>{master_line}{note_line}"
            ),
        )
    except Exception as exc:
        logger.warning("Failed to notify client %s: %s", tg_uid, exc)
