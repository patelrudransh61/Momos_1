import os
import sqlite3
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8610917014:AAEj59k4kQIkNVzK2wNJbr7uDXXXLnuU-aY")

ADMIN_ID = 6419105535

CHANNELS = [
    ("Channel 1", "https://t.me/tiranga_team"),
    ("Channel 2", "https://t.me/+wgeCmoTWqNkwMWI1"),
    ("Channel 3", "https://t.me/+uZvwC03tydliNWM1"),
    ("Channel 4", "https://t.me/+H-HihRds5zpkZGFl"),
    ("Channel 5", "https://t.me/public_sg_community"),
    ("Channel 6", "https://t.me/public_sg_updated"),
]

DB = "bot.db"


# =========================
# DATABASE
# =========================

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_users():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()

    return [row[0] for row in rows]


def save_video(file_id):
    conn = sqlite3.connect(DB)

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("video_file_id", file_id)
    )

    conn.commit()
    conn.close()


def get_video():
    conn = sqlite3.connect(DB)

    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        ("video_file_id",)
    ).fetchone()

    conn.close()

    return row[0] if row else None


# =========================
# CHANNEL BUTTONS
# =========================

def channel_keyboard():

    buttons = []

    for name, link in CHANNELS:
        buttons.append([
            InlineKeyboardButton(
                f"📢 {name}",
                url=link
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify"
        )
    ])

    return InlineKeyboardMarkup(buttons)


# =========================
# CHECK MEMBERSHIP
# =========================

async def is_member(bot, user_id, channel):

    try:
        member = await bot.get_chat_member(
            chat_id=channel,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception:
        return False


async def check_all_channels(bot, user_id):

    for name, channel in CHANNELS:

        if not await is_member(bot, user_id, channel):
            return False, name

    return True, None


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user.id)

    await update.message.reply_text(
        "🔥 Welcome!\n\n"
        "Bot use karne ke liye neeche diye gaye "
        "6 channels join karo.\n\n"
        "Join karne ke baad ✅ Verify dabao.",
        reply_markup=channel_keyboard()
    )


# =========================
# VERIFY
# =========================

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    success, missing = await check_all_channels(
        context.bot,
        user_id
    )

    if not success:

        await query.message.reply_text(
            f"❌ Verification failed!\n\n"
            f"Abhi `{missing}` join nahi hua hai.\n\n"
            f"Sabhi channels join karke dobara Verify karo.",
            reply_markup=channel_keyboard()
        )

        return

    # Save user after successful verification
    add_user(user_id)

    video_id = get_video()

    if not video_id:

        await query.message.reply_text(
            "✅ Verification successful!\n\n"
            "Lekin abhi admin ne video upload nahi ki hai."
        )

        return

    await context.bot.send_video(
        chat_id=user_id,
        video=video_id,
        caption="🎥 Enjoy!"
    )


# =========================
# ADMIN VIDEO UPLOAD
# =========================

async def admin_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.video:
        return

    file_id = update.message.video.file_id

    save_video(file_id)

    await update.message.reply_text(
        "✅ Video successfully saved!\n\n"
        "Ab verified users ko /start → Verify ke baad "
        "ye video automatically milegi."
    )


# =========================
# BROADCAST
# =========================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ You are not authorized."
        )
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "⚠️ Kisi message/video ko reply karke:\n\n"
            "/broadcast\n\n"
            "bhejo."
        )

        return

    message = update.message.reply_to_message

    users = get_users()

    sent = 0
    failed = 0

    await update.message.reply_text(
        f"📢 Broadcast started...\n"
        f"Users: {len(users)}"
    )

    for user_id in users:

        try:

            await message.copy(
                chat_id=user_id
            )

            sent += 1

            # Telegram rate limit se bachne ke liye
            await asyncio.sleep(0.05)

        except Exception:

            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast completed!\n\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}"
    )


# =========================
# ADMIN COMMAND
# =========================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "👑 Admin Panel\n\n"
        "🎥 Bot ko video bhejo → automatically save ho jayegi.\n\n"
        "📢 Broadcast:\n"
        "Kisi message/video ko reply karo aur /broadcast bhejo."
    )


# =========================
# MAIN
# =========================

def main():

    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("admin", admin)
    )

    app.add_handler(
        CommandHandler("broadcast", broadcast)
    )

    app.add_handler(
        CallbackQueryHandler(
            verify,
            pattern="^verify$"
        )
    )

    # Admin video handler
    app.add_handler(
        MessageHandler(
            filters.VIDEO,
            admin_video
        )
    )

    print("Bot started...")

    app.run_polling()


if __name__ == "__main__":
    main()
