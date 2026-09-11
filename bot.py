import asyncio
import uuid
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# আপনার বটের টোকেন
BOT_TOKEN = "8949748635:AAEd7NKUfclKij86C_qHiLz4bCbRrbRrFAI"

# স্টেট নির্ধারণ
WAITING_FOR_URL = 1

# ব্যাকগ্রাউন্ড শিডিউলার
scheduler = AsyncIOScheduler()
scheduler.start()

# ব্যবহারকারীদের ক্রন জবের তথ্য সংরক্ষণের ডিকশনারি
user_jobs = {}

# ব্যাকগ্রাউন্ডে লিঙ্ক হিট/ভিউ করার ফাংশন
async def ping_url(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                pass
    except Exception:
        pass

# মেইন মেনু বাটন
def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Cron Job", callback_data="btn_add_job"),
            InlineKeyboardButton("❌ Remove Cron Job", callback_data="btn_remove_job"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "স্বাগতম! ক্রন জব পরিচালনা করতে নিচের যেকোনো একটি বাটন বেছে নিন:"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_keyboard())
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=get_main_keyboard())
    return ConversationHandler.END

# 'Add Cron Job' হ্যান্ডলার
async def add_job_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("অনুগ্রহ করে যে লিংকটি ভিউ করতে চান সেটি পাঠান (যেমন: https://example.com):")
    return WAITING_FOR_URL

# লিংক গ্রহণ ও সময় নির্বাচনের বাটন তৈরি
async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("ভুল লিংক! অনুগ্রহ করে সঠিক URL পাঠান (http:// বা https:// সহ):")
        return WAITING_FOR_URL

    context.user_data["target_url"] = url

    # নির্দিষ্ট সময়ের ইন্টারভাল বাটন
    intervals = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 100]
    keyboard = []
    row = []
    for sec in intervals:
        row.append(InlineKeyboardButton(f"{sec}s", callback_data=f"set_sec_{sec}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"লিংক যুক্ত হয়েছে:\n`{url}`\n\nকত সেকেন্ড পর পর ভিউ করতে চান নির্বাচন করুন:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )
    return ConversationHandler.END

# সময় নির্বাচন ও জব চালু
async def set_interval_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    seconds = int(query.data.replace("set_sec_", ""))
    url = context.user_data.get("target_url")
    user_id = query.from_user.id

    if not url:
        await query.edit_message_text("লিংক পাওয়া যায়নি। আবার চেষ্টা করুন।", reply_markup=get_main_keyboard())
        return

    job_id = f"job_{uuid.uuid4().hex[:8]}"

    # ব্যাকগ্রাউন্ড শিডিউলারে যোগ করা
    scheduler.add_job(
        ping_url,
        "interval",
        seconds=seconds,
        args=[url],
        id=job_id,
        max_instances=10,
    )

    if user_id not in user_jobs:
        user_jobs[user_id] = []

    user_jobs[user_id].append({"id": job_id, "url": url, "interval": seconds})

    text = (
        f"✅ **ক্রন জব সফলভাবে চালু হয়েছে!**\n\n"
        f"🌐 **লিংক:** `{url}`\n"
        f"⏱ **বিরতি:** প্রতি {seconds} সেকেন্ড পর পর ভিউ হবে।"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# 'Remove Cron Job' মেনু প্রদর্শন
async def remove_job_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    jobs = user_jobs.get(user_id, [])
    if not jobs:
        keyboard = [[InlineKeyboardButton("🔙 ফিরে যান", callback_data="btn_back_main")]]
        await query.edit_message_text("আপনার কোনো সক্রিয় ক্রন জব চালু নেই।", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for idx, job in enumerate(jobs, 1):
        short_url = job["url"][:22] + "..." if len(job["url"]) > 25 else job["url"]
        btn_text = f"{idx}. {short_url} ({job['interval']}s)"
        keyboard.append([InlineKeyboardButton(f"❌ {btn_text}", callback_data=f"del_{job['id']}")])

    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="btn_back_main")])
    await query.edit_message_text(
        "যে ক্রন জবটি ডিলিট করতে চান সেটির উপর ক্লিক করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ক্রন জব মুছে ফেলা
async def delete_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    job_id = query.data.replace("del_", "")

    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    if user_id in user_jobs:
        user_jobs[user_id] = [j for j in user_jobs[user_id] if j["id"] != job_id]

    await query.edit_message_text("🗑 ক্রন জবটি সফলভাবে রিমুভ করা হয়েছে!", reply_markup=get_main_keyboard())

# প্রধান অ্যাপ রানার
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_job_start, pattern="^btn_add_job$")],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(set_interval_and_start, pattern="^set_sec_"))
    application.add_handler(CallbackQueryHandler(remove_job_menu, pattern="^btn_remove_job$"))
    application.add_handler(CallbackQueryHandler(delete_job, pattern="^del_"))
    application.add_handler(CallbackQueryHandler(start, pattern="^btn_back_main$"))

    application.run_polling()

if __name__ == "__main__":
    main()
