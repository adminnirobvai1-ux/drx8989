import os
import asyncio
import uuid
import random
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

BOT_TOKEN = os.getenv("BOT_TOKEN", "8949748635:AAEd7NKUfclKij86C_qHiLz4bCbRrbRrFAI")
WAITING_FOR_URL = 1

scheduler = AsyncIOScheduler()
user_jobs = {}

# রিয়েল ব্রাউজার ইউজার-এজেন্ট তালিকা
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# রিয়েল লাইভ হিট ও ভিউ কাউন্ট ফাংশন
async def ping_url(url: str):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "X-Forwarded-For": f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), ssl=False) as response:
                await response.read()
    except Exception:
        pass

def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⚡ Add Cron Job", callback_data="btn_add_job"),
            InlineKeyboardButton("🗑 Remove Cron Job", callback_data="btn_remove_job"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# মেইন ড্যাশবোর্ড ডিজাইন
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╔══════════════════════╗\n"
        "   🚀 **CRON JOB CONTROLLER**\n"
        "╚══════════════════════╝\n\n"
        "🌐 **Engine:** Real-Time Traffic Booster\n"
        "📡 **Protocol:** HTTP/2 Supported\n"
        "📊 **Status:** Active & Ready\n\n"
        "নিচের বাটন চেপে আপনার টাস্ক পরিচালনা করুন:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def add_job_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "╔══════════════════════╗\n"
        "   🔗 **TARGET LINK SETUP**\n"
        "╚══════════════════════╝\n\n"
        "অনুগ্রহ করে যে লিংকটি রিয়েল-টাইমে কল করতে চান সেটি পাঠান:\n\n"
        "📌 *উদাহরণ:* `https://example.com`"
    )
    await query.edit_message_text(text, parse_mode="Markdown")
    return WAITING_FOR_URL

async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ **ভুল URL!** অনুগ্রহ করে `http://` অথবা `https://` সহ সঠিক লিংক দিন:")
        return WAITING_FOR_URL

    context.user_data["target_url"] = url

    intervals = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 100]
    keyboard = []
    row = []
    for sec in intervals:
        row.append(InlineKeyboardButton(f"⚡ {sec}s", callback_data=f"set_sec_{sec}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    text = (
        "╔══════════════════════╗\n"
        "   ⏱ **SET TIME INTERVAL**\n"
        "╚══════════════════════╝\n\n"
        f"🎯 **Target:** `{url}`\n\n"
        "প্রতি কত সেকেন্ড পর পর রিয়েল কল পাঠাতে চান নির্বাচন করুন:"
    )

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def set_interval_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    seconds = int(query.data.replace("set_sec_", ""))
    url = context.user_data.get("target_url")
    user_id = query.from_user.id

    if not url:
        await query.edit_message_text("❌ লিংক পাওয়া যায়নি! পুনরায় চেষ্টা করুন।", reply_markup=get_main_keyboard())
        return

    job_id = f"job_{uuid.uuid4().hex[:8]}"

    scheduler.add_job(
        ping_url,
        "interval",
        seconds=seconds,
        args=[url],
        id=job_id,
        max_instances=50,
    )

    if user_id not in user_jobs:
        user_jobs[user_id] = []

    user_jobs[user_id].append({"id": job_id, "url": url, "interval": seconds})

    text = (
        "╔══════════════════════╗\n"
        "   🟢 **JOB ACTIVATED LIVE!**\n"
        "╚══════════════════════╝\n\n"
        f"🌐 **Target URL:**\n`{url}`\n\n"
        f"⚡ **Interval:** প্রতি `{seconds}s` পরপর লাইভ কল পাঠানো হচ্ছে\n"
        f"🛡 **Mode:** Real Browser Emulation (Anti-Bot Bypass)\n"
        f"🆔 **Job ID:** `{job_id}`\n\n"
        "✅ ব্যাকগ্রাউন্ডে সফলভাবে কল চালু হয়েছে।"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def remove_job_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    jobs = user_jobs.get(user_id, [])
    if not jobs:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_back_main")]]
        text = (
            "╔══════════════════════╗\n"
            "   ⚠️ **NO RUNNING JOBS**\n"
            "╚══════════════════════╝\n\n"
            "আপনার বর্তমানে কোনো রিয়েল-টাইম জব চালু নেই।"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    keyboard = []
    for idx, job in enumerate(jobs, 1):
        domain = job["url"].split("//")[-1][:18]
        btn_text = f"❌ [{idx}] {domain}... ({job['interval']}s)"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"del_{job['id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_back_main")])
    text = (
        "╔══════════════════════╗\n"
        "   🗑 **ACTIVE CRON JOBS**\n"
        "╚══════════════════════╝\n\n"
        "যে ক্রন জবটি বন্ধ করতে চান সেটির উপর ক্লিক করুন:"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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

    text = (
        "╔══════════════════════╗\n"
        "   🗑 **JOB TERMINATED**\n"
        "╚══════════════════════╝\n\n"
        f"🆔 **Job ID:** `{job_id}`\n"
        "✅ রিয়েল-টাইম কল সফলভাবে বন্ধ করা হয়েছে।"
    )
    await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def post_init(application: Application):
    if not scheduler.running:
        scheduler.start()

def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

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
