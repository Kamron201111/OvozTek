import os
import logging
import asyncio
import json
import pandas as pd

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from parser import fetch_page
from db import init_db, add_votes, search_phone, count_votes, get_all_votes, clear_votes, get_stats

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan!")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID muhit o'zgaruvchisi o'rnatilmagan!")

# ─── Bot & Dispatcher ─────────────────────────────────────────────────────────
bot       = Bot(token=BOT_TOKEN)
storage   = MemoryStorage()
dp        = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

# ─── FSM ─────────────────────────────────────────────────────────────────────
class SearchState(StatesGroup):
    waiting_phone = State()

class ApiState(StatesGroup):
    waiting_api = State()

# ─── Keyboard ─────────────────────────────────────────────────────────────────
def main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Yuklash"),   KeyboardButton(text="🔎 Qidirish")],
            [KeyboardButton(text="📄 Excel"),      KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="⚙️ Admin panel")],
        ],
        resize_keyboard=True,
    )
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 API o'zgartirish"), KeyboardButton(text="🗑 Bazani tozalash")],
            [KeyboardButton(text="🔄 Restart"),           KeyboardButton(text="◀️ Orqaga")],
        ],
        resize_keyboard=True,
    )
    return kb

# ─── Helpers ──────────────────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def admin_only(func):
    """Decorator — faqat admin uchun."""
    import functools
    @functools.wraps(func)
    async def wrapper(msg: types.Message, **kwargs):
        if not is_admin(msg.from_user.id):
            await msg.answer("❌ Bu buyruq faqat admin uchun!")
            return
        return await func(msg, **kwargs)
    return wrapper

# ─── /start ───────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Bu bot faqat admin uchun mo'ljallangan.")
        return
    await msg.answer(
        "👋 Assalomu alaykum!\n"
        "OpenBudget Ovoz Kuzatuvchi botga xush kelibsiz.\n\n"
        "Quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu(),
    )

# ─── Yuklash ──────────────────────────────────────────────────────────────────
@dp.message(lambda m: m.text == "📥 Yuklash")
@admin_only
async def load_votes(msg: types.Message):
    status_msg = await msg.answer("⏳ Yuklanmoqda, iltimos kuting...")
    total = 0
    errors = 0

    for page in range(0, 500):
        try:
            votes = fetch_page(page)
        except Exception as e:
            logger.error(f"Page {page} xatolik: {e}")
            errors += 1
            if errors >= 5:
                logger.warning("5 ta ketma-ket xatolik — yuklash to'xtatildi.")
                break
            continue

        if not votes:
            break  # oxirgi sahifa

        added = add_votes(votes)
        total += added
        errors = 0  # xatolik yo'q, reset

        # Har 50 sahifada progress ko'rsat
        if page % 50 == 0 and page > 0:
            try:
                await status_msg.edit_text(f"⏳ {page}-sahifa... {total} ta yangi ovoz saqlandi.")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Yuklash tugadi!\n"
        f"📊 Yangi saqlangan ovozlar: {total} ta\n"
        f"💾 Bazadagi jami ovozlar: {count_votes()} ta"
    )

# ─── Qidirish ─────────────────────────────────────────────────────────────────
@dp.message(lambda m: m.text == "🔎 Qidirish")
@admin_only
async def ask_search(msg: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_phone)
    await msg.answer("📱 Telefon raqamning oxirgi 4–9 raqamini yuboring:\n\nMisol: <code>901234567</code>", parse_mode="HTML")

@dp.message(SearchState.waiting_phone)
async def do_search(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return

    query = msg.text.strip()
    if not query.isdigit():
        await msg.answer("❌ Faqat raqam yuboring.")
        return

    await state.clear()
    results = search_phone(query)

    if not results:
        await msg.answer(f"🔍 <code>{query}</code> bo'yicha hech narsa topilmadi.", parse_mode="HTML")
        return

    lines = [f"✅ <b>{len(results)} ta natija topildi</b> (<code>{query}</code>):\n"]
    for phone, date in results[:20]:  # maksimal 20 ta
        lines.append(f"📞 <code>{phone}</code>  🗓 {date}")
    if len(results) > 20:
        lines.append(f"\n... va yana {len(results) - 20} ta")

    await msg.answer("\n".join(lines), parse_mode="HTML")

# ─── Statistika ───────────────────────────────────────────────────────────────
@dp.message(lambda m: m.text == "📊 Statistika")
@admin_only
async def show_stat(msg: types.Message):
    stats = get_stats()
    await msg.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"🗳 Jami ovozlar: <b>{stats['total']:,}</b>\n"
        f"📅 Eng yangi ovoz: <b>{stats['latest'] or 'Ma\'lumot yo\'q'}</b>\n"
        f"📅 Eng eski ovoz: <b>{stats['oldest'] or 'Ma\'lumot yo\'q'}</b>",
        parse_mode="HTML",
    )

# ─── Excel ────────────────────────────────────────────────────────────────────
@dp.message(lambda m: m.text == "📄 Excel")
@admin_only
async def send_excel(msg: types.Message):
    await msg.answer("⏳ Excel fayl tayyorlanmoqda...")
    try:
        data = get_all_votes()
        if not data:
            await msg.answer("❌ Bazada ma'lumot yo'q.")
            return

        df = pd.DataFrame(data, columns=["Telefon", "Sana"])
        file_path = "/tmp/ovozlar.xlsx"
        df.to_excel(file_path, index=False)

        await msg.answer_document(
            types.FSInputFile(file_path, filename="ovozlar.xlsx"),
            caption=f"📄 Jami {len(data):,} ta ovoz",
        )
    except Exception as e:
        logger.error(f"Excel xatolik: {e}")
        await msg.answer(f"❌ Xatolik yuz berdi: {e}")

# ─── Admin panel ──────────────────────────────────────────────────────────────
@dp.message(lambda m: m.text == "⚙️ Admin panel")
@admin_only
async def admin_panel(msg: types.Message):
    await msg.answer("⚙️ <b>Admin panel</b>", parse_mode="HTML", reply_markup=admin_menu())

@dp.message(lambda m: m.text == "◀️ Orqaga")
@admin_only
async def back_to_main(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("🏠 Asosiy menyu", reply_markup=main_menu())

# API o'zgartirish
@dp.message(lambda m: m.text == "🔑 API o'zgartirish")
@admin_only
async def ask_api(msg: types.Message, state: FSMContext):
    await state.set_state(ApiState.waiting_api)
    await msg.answer("🔑 Yangi API ID ni yuboring:")

@dp.message(ApiState.waiting_api)
async def set_api(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return
    new_api = msg.text.strip()
    try:
        with open("config.json", "w") as f:
            json.dump({"api": new_api}, f)
        await state.clear()
        await msg.answer(f"✅ API yangilandi: <code>{new_api}</code>", parse_mode="HTML")
    except Exception as e:
        await msg.answer(f"❌ Xatolik: {e}")

# Bazani tozalash
@dp.message(lambda m: m.text == "🗑 Bazani tozalash")
@admin_only
async def confirm_clear(msg: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Ha, tozala"), KeyboardButton(text="❌ Yo'q, bekor qil")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await msg.answer("⚠️ Haqiqatan ham bazani to'liq tozalamoqchimisiz?", reply_markup=kb)

@dp.message(lambda m: m.text == "✅ Ha, tozala")
@admin_only
async def do_clear(msg: types.Message):
    try:
        clear_votes()
        await msg.answer("🗑 Baza muvaffaqiyatli tozalandi.", reply_markup=admin_menu())
    except Exception as e:
        await msg.answer(f"❌ Xatolik: {e}")

@dp.message(lambda m: m.text == "❌ Yo'q, bekor qil")
@admin_only
async def cancel_clear(msg: types.Message):
    await msg.answer("✅ Bekor qilindi.", reply_markup=admin_menu())

# Restart
@dp.message(lambda m: m.text == "🔄 Restart")
@admin_only
async def restart_bot(msg: types.Message):
    await msg.answer("🔄 Bot qayta ishga tushirilmoqda...")
    import os, signal
    os.kill(os.getpid(), signal.SIGTERM)

# ─── Auto-update (scheduler) ──────────────────────────────────────────────────
async def auto_update():
    """Har 30 daqiqada birinchi sahifani yangilaydi."""
    try:
        votes = fetch_page(0)
        if votes:
            added = add_votes(votes)
            if added:
                logger.info(f"Auto-update: {added} ta yangi ovoz qo'shildi.")
    except Exception as e:
        logger.error(f"Auto-update xatolik: {e}")

# ─── Startup / Shutdown ───────────────────────────────────────────────────────
async def on_startup():
    init_db()
    scheduler.add_job(auto_update, "interval", minutes=30)
    scheduler.start()
    logger.info("Bot ishga tushdi ✅")
    try:
        await bot.send_message(ADMIN_ID, "🟢 Bot ishga tushdi!")
    except Exception:
        pass

async def on_shutdown():
    scheduler.shutdown(wait=False)
    logger.info("Bot to'xtatildi.")
    try:
        await bot.send_message(ADMIN_ID, "🔴 Bot to'xtatildi.")
    except Exception:
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    await on_startup()
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
