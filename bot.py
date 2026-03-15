import os
import logging
import asyncio
import json
import signal
import pandas as pd

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from parser import fetch_page, get_api
from db import init_db, add_votes, search_phone, count_votes, get_all_votes, clear_votes, get_stats

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Env ──────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN o'rnatilmagan!")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID o'rnatilmagan!")

# ─── Bot ──────────────────────────────────────────────────────────────────────
bot       = Bot(token=BOT_TOKEN)
dp        = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

# ─── FSM ──────────────────────────────────────────────────────────────────────
class Form(StatesGroup):
    search        = State()
    new_api       = State()
    confirm_clear = State()

# ─── Klaviatura ───────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Yuklash"),      KeyboardButton(text="🔎 Qidirish")],
            [KeyboardButton(text="📄 Excel"),         KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="⚙️ Admin panel")],
        ],
        resize_keyboard=True,
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 API o'zgartirish"), KeyboardButton(text="🗑 Bazani tozalash")],
            [KeyboardButton(text="🔄 Restart"),            KeyboardButton(text="◀️ Orqaga")],
        ],
        resize_keyboard=True,
    )

def confirm_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Ha, tozala"), KeyboardButton(text="❌ Bekor qil")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# ─── Helper ───────────────────────────────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

# ─── /start ───────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Bu bot faqat admin uchun.")
        return
    await msg.answer(
        "👋 Assalomu alaykum!\n"
        "OpenBudget Ovoz Kuzatuvchi botga xush kelibsiz.\n\n"
        "Tugmalardan birini tanlang:",
        reply_markup=main_kb(),
    )

# ─── Yuklash ──────────────────────────────────────────────────────────────────
@dp.message(F.text == "📥 Yuklash")
async def load_votes(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    status = await msg.answer(
        f"⏳ Yuklanmoqda...\n"
        f"🔗 API: <code>{get_api()}</code>",
        parse_mode="HTML",
    )
    total  = 0
    errors = 0

    for page in range(0, 2000):
        try:
            votes = fetch_page(page)
        except Exception as e:
            logger.error(f"Page {page} kutilmagan xato: {e}")
            errors += 1
            if errors >= 5:
                logger.warning("5 ta xato — yuklash to'xtatildi.")
                break
            continue

        if not votes:
            # Bo'sh sahifa = barcha ovozlar yuklandi
            break

        added  = add_votes(votes)
        total += added
        errors = 0

        # Har 10 sahifada progress ko'rsat
        if page > 0 and page % 10 == 0:
            try:
                await status.edit_text(
                    f"⏳ {page}-sahifa yuklanmoqda...\n"
                    f"🆕 Yangi ovozlar: {total} ta",
                )
            except Exception:
                pass

    await status.edit_text(
        f"✅ Yuklash tugadi!\n\n"
        f"🆕 Yangi saqlangan: <b>{total}</b> ta\n"
        f"💾 Bazada jami: <b>{count_votes():,}</b> ta",
        parse_mode="HTML",
    )

# ─── Qidirish ─────────────────────────────────────────────────────────────────
@dp.message(F.text == "🔎 Qidirish")
async def ask_search(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(Form.search)
    await msg.answer(
        "📱 Telefon raqamning oxirgi raqamlarini yuboring:\n\n"
        "Misol: <code>901234567</code> yoki <code>4567</code>",
        parse_mode="HTML",
    )

@dp.message(Form.search)
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
        await msg.answer(
            f"🔍 <code>{query}</code> bo'yicha hech narsa topilmadi.\n"
            f"Avval <b>📥 Yuklash</b> ni bosing.",
            parse_mode="HTML",
            reply_markup=main_kb(),
        )
        return
    lines = [f"✅ <b>{len(results)} ta natija</b> (<code>{query}</code>):\n"]
    for phone, date in results[:20]:
        lines.append(f"📞 <code>{phone}</code>  🗓 {date}")
    if len(results) > 20:
        lines.append(f"\n... va yana {len(results)-20} ta")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_kb())

# ─── Statistika ───────────────────────────────────────────────────────────────
@dp.message(F.text == "📊 Statistika")
async def show_stat(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    s = get_stats()
    await msg.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"🗳 Jami ovozlar: <b>{s['total']:,}</b>\n"
        f"📅 Eng yangi:    <b>{s['latest'] or 'Mavjud emas'}</b>\n"
        f"📅 Eng eski:     <b>{s['oldest'] or 'Mavjud emas'}</b>\n\n"
        f"🔗 Faol API: <code>{get_api()}</code>",
        parse_mode="HTML",
    )

# ─── Excel ────────────────────────────────────────────────────────────────────
@dp.message(F.text == "📄 Excel")
async def send_excel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    wait = await msg.answer("⏳ Excel tayyorlanmoqda...")
    try:
        data = get_all_votes()
        if not data:
            await wait.edit_text(
                "❌ Bazada ma'lumot yo'q.\n"
                "Avval <b>📥 Yuklash</b> ni bosing.",
                parse_mode="HTML",
            )
            return
        df = pd.DataFrame(data, columns=["Telefon", "Sana"])
        path = "/tmp/ovozlar.xlsx"
        df.to_excel(path, index=False)
        await wait.delete()
        await msg.answer_document(
            types.FSInputFile(path, filename="ovozlar.xlsx"),
            caption=f"📄 Jami <b>{len(data):,}</b> ta ovoz",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Excel xato: {e}")
        await wait.edit_text(f"❌ Xato: {e}")

# ─── Admin panel ──────────────────────────────────────────────────────────────
@dp.message(F.text == "⚙️ Admin panel")
async def admin_panel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        f"⚙️ <b>Admin panel</b>\n\n"
        f"🔗 Faol API: <code>{get_api()}</code>\n"
        f"💾 Bazada: <b>{count_votes():,}</b> ta ovoz",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )

@dp.message(F.text == "◀️ Orqaga")
async def back_main(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("🏠 Asosiy menyu", reply_markup=main_kb())

# ─── API o'zgartirish ─────────────────────────────────────────────────────────
@dp.message(F.text == "🔑 API o'zgartirish")
async def ask_api(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(Form.new_api)
    await msg.answer(
        f"🔑 Hozirgi API: <code>{get_api()}</code>\n\n"
        f"Yangi API ID ni yuboring:\n"
        f"(openbudget.uz Network tab dan oling)",
        parse_mode="HTML",
    )

@dp.message(Form.new_api)
async def save_api(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return
    new_api = msg.text.strip()
    try:
        with open("config.json", "w") as f:
            json.dump({"api": new_api}, f)
        await state.clear()
        await msg.answer(
            f"✅ API yangilandi!\n\n"
            f"Yangi API: <code>{new_api}</code>\n\n"
            f"Endi <b>📥 Yuklash</b> bosing.",
            parse_mode="HTML",
            reply_markup=admin_kb(),
        )
    except Exception as e:
        await msg.answer(f"❌ Xato: {e}")

# ─── Bazani tozalash ──────────────────────────────────────────────────────────
@dp.message(F.text == "🗑 Bazani tozalash")
async def ask_clear(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(Form.confirm_clear)
    await msg.answer(
        f"⚠️ Haqiqatan ham bazani to'liq tozalamoqchimisiz?\n"
        f"Bazada hozir <b>{count_votes():,}</b> ta ovoz bor.",
        parse_mode="HTML",
        reply_markup=confirm_kb(),
    )

@dp.message(Form.confirm_clear, F.text == "✅ Ha, tozala")
async def do_clear(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return
    clear_votes()
    await state.clear()
    await msg.answer("🗑 Baza tozalandi.", reply_markup=admin_kb())

@dp.message(Form.confirm_clear, F.text == "❌ Bekor qil")
async def cancel_clear(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return
    await state.clear()
    await msg.answer("✅ Bekor qilindi.", reply_markup=admin_kb())

# ─── Restart ──────────────────────────────────────────────────────────────────
@dp.message(F.text == "🔄 Restart")
async def restart_bot(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("🔄 Qayta ishga tushirilmoqda...", reply_markup=main_kb())
    os.kill(os.getpid(), signal.SIGTERM)

# ─── Auto-update (har 30 daqiqa) ─────────────────────────────────────────────
async def auto_update():
    """Faqat birinchi sahifani tekshiradi — yangi ovozlar bormi."""
    try:
        votes = fetch_page(0)
        if votes:
            added = add_votes(votes)
            if added:
                logger.info(f"Auto-update: {added} ta yangi ovoz qo'shildi.")
    except Exception as e:
        logger.error(f"Auto-update xato: {e}")

# ─── Startup / Shutdown ───────────────────────────────────────────────────────
async def on_startup():
    init_db()
    scheduler.add_job(auto_update, "interval", minutes=30)
    scheduler.start()
    logger.info("Bot ishga tushdi ✅")
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🟢 Bot ishga tushdi!\n"
            f"🔗 API: <code>{get_api()}</code>\n"
            f"💾 Bazada: <b>{count_votes():,}</b> ta ovoz",
            parse_mode="HTML",
        )
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
