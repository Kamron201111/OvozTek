# OvozTek Bot 🗳

OpenBudget.uz ovozlarini kuzatuvchi Telegram bot.

## Imkoniyatlari
- 📥 Barcha ovozlarni API dan yuklash (dublikatsiz)
- 🔎 Telefon raqam oxirgi raqamlari bo'yicha qidirish (50 tagacha natija)
- 📊 Statistika (jami, eng yangi, eng eski ovoz)
- 📄 Excel eksport
- 🔄 Har 30 daqiqada avtomatik yangilanish
- ⚙️ Admin panel: API almashtirish, bazani tozalash, restart

## Railway ga deploy qilish

### 1. Muhit o'zgaruvchilarini o'rnating
Railway → Variables bo'limiga qo'shing:

| O'zgaruvchi | Qiymat |
|-------------|--------|
| `BOT_TOKEN` | BotFather dan olingan token |
| `ADMIN_ID`  | Sizning Telegram ID (raqam) |

### 2. Deploy
```bash
git add .
git commit -m "deploy"
git push
```

Railway avtomatik `Procfile` dagi `worker: python bot.py` ni ishga tushiradi.

## Muhim eslatma
Railway volumesiz ishlaydi — `votes.db` restart bo'lganda o'chishi mumkin.
Doimiy saqlash kerak bo'lsa Railway Volumes yoqing yoki Supabase/PostgreSQL ga o'ting.
