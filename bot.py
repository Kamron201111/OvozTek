
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from parser import fetch_page
from db import init_db, add_votes, search_phone, count_votes, get_all_votes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

API_BASE = "https://openbudget.uz/api/v2/info/votes/69b6f9b83d01cb2096d874bf"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("📥 Yuklash"))
menu.add(KeyboardButton("🔎 Qidirish"))
menu.add(KeyboardButton("📄 Excel"))
menu.add(KeyboardButton("📊 Stat"))

def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Bot faqat admin uchun.")
    await msg.reply("OpenBudget bot ishga tushdi", reply_markup=menu)

@dp.message_handler(lambda m: m.text == "📥 Yuklash")
async def load_votes(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    total = 0
    for page in range(0, 300):
        votes = fetch_page(page)
        if not votes:
            break
        add_votes(votes)
        total += len(votes)
    await msg.reply(f"Yuklandi: {total} ta ovoz")

@dp.message_handler(lambda m: m.text == "🔎 Qidirish")
async def ask_search(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.reply("Oxirgi 6 raqamni yuboring")

@dp.message_handler(lambda m: m.text.isdigit() and len(m.text) >= 4)
async def search(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    res = search_phone(msg.text)
    if res:
        await msg.reply(f"Topildi: {res[0]} | {res[1]}")
    else:
        await msg.reply("Topilmadi")

@dp.message_handler(lambda m: m.text == "📊 Stat")
async def stat(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    c = count_votes()
    await msg.reply(f"Bazada: {c} ta ovoz")

@dp.message_handler(lambda m: m.text == "📄 Excel")
async def excel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    import pandas as pd
    data = get_all_votes()
    df = pd.DataFrame(data, columns=["phone","date"])
    file = "votes.xlsx"
    df.to_excel(file, index=False)
    await msg.reply_document(open(file,"rb"))

async def auto_update():
    votes = fetch_page(0)
    if votes:
        add_votes(votes)

def start_scheduler():
    scheduler.add_job(auto_update, "interval", minutes=1)
    scheduler.start()

if __name__ == "__main__":
    init_db()
    start_scheduler()
    executor.start_polling(dp, skip_updates=True)
