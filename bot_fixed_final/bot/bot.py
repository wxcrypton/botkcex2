import asyncio
import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
import random
import re

# توکن ربات شما (باید در محیط تنظیم شود)
TOKEN = os.getenv("TOKEN")

# اطلاعات دیتابیس PostgreSQL
DATABASE_URL = "postgresql://bot_user:kT6mEIstLOzoh95FlXeGfSQ2cfBVIq15@dpg-cusngkjtq21c73b69gmfg-a:5432/bot_database_r6me"

# شناسه کاربری شما (ایدی عددی شما در تلگرام)
ADMIN_IDS = [5092758824, 7754882804]

# گروهی که اکانت‌ها به آن ارسال می‌شوند
GROUP_ID = -1002453133373  # مقدار را با آی‌دی عددی گروه خود جایگزین کنید

# حالت‌های ربات
AWAITING_PHONE_NUMBER = 1
AWAITING_EMAIL = 2
AWAITING_PASSWORD = 3
AWAITING_WITHDRAWAL_INFO = 4

# ایجاد اتصال به دیتابیس PostgreSQL
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

# ایجاد جداول در PostgreSQL اگر وجود نداشته باشند
cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE,
        referred_by BIGINT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS balances (
        user_id BIGINT PRIMARY KEY,
        balance BIGINT DEFAULT 0
    )
''')
conn.commit()

async def save_user(user_id):
    cursor.execute('SELECT user_id FROM referrals WHERE user_id = %s', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO referrals (user_id, referred_by) VALUES (%s, %s)', (user_id, None))
        conn.commit()
    cursor.execute('SELECT user_id FROM balances WHERE user_id = %s', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO balances (user_id, balance) VALUES (%s, %s)', (user_id, 0))
        conn.commit()

async def send_main_menu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await save_user(user_id)
    
    keyboard = [
        [KeyboardButton("📖 آموزش ثبت نام")],
        [KeyboardButton("🔗 لینک زیرمجموعه‌گیری"), KeyboardButton("📊 تعداد زیرمجموعه‌ها")],
        [KeyboardButton("📋 لیست زیرمجموعه‌ها"), KeyboardButton("👤 حساب کاربری")],
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton("📢 ارسال پیام به همه"), KeyboardButton("📊 تعداد کل کاربران")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔘 منو برای دستورات ربات فعال شد.", reply_markup=reply_markup)

async def handle_text_buttons(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    user_id = update.effective_user.id
    await save_user(user_id)
    
    text = update.message.text
    
    if text == "📖 آموزش ثبت نام":
        await send_registration_messages(update, context)
    elif text == "🔗 لینک زیرمجموعه‌گیری":
        await referral_command(update, context)
    elif text == "📊 تعداد زیرمجموعه‌ها":
        await my_referrals_command(update, context)
    elif text == "📋 لیست زیرمجموعه‌ها":
        await list_referrals_command(update, context)
    elif text == "👤 حساب کاربری":
        await show_account_menu(update, context)
    elif text == "📢 ارسال پیام به همه" and user_id in ADMIN_IDS:
        await update.message.reply_text("📩 لطفاً پیام خود را ارسال کنید.")
        context.user_data['awaiting_broadcast'] = True
    elif text == "📊 تعداد کل کاربران" and user_id in ADMIN_IDS:
        await get_total_users(update, context)
    elif text == "🔙 بازگشت":
        await send_main_menu(update, context)

async def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", send_main_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    print("✅ Bot is running and connected to PostgreSQL...")

    await asyncio.sleep(3)  # جلوگیری از گیر کردن در Render

    await application.updater.stop()
    await application.stop()
    await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
