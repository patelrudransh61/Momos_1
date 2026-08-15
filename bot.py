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

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8610917014:AAEj59k4kQIkNVzK2wNJbr7uDXXXLnuU-aY")

ADMIN_ID = 6419105535

CHANNELS = [
    ("Channel 1", "https://t.me/team_tiranga", "@team_tiranga"),
    ("Channel 2", "https://t.me/public_sg_community", "@public_sg_community"),
    ("Channel 3", "https://t.me/public_sg_updated", "@public_sg_updated"),
    ("Channel 4", "https://t.me/Sparks_Corporation", "@Sparks_Corporation"),
    ("Channel 5", "https://t.me/check_momos_1", "@check_momos_1"),
    ("Channel 6", "https://t.me/check_momos_2", "@check_momos_2"),
]

DB = "bot.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB)


def init_db():
    conn = get_db()
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
    conn = get_db()

    conn.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )

    conn.commit()
    conn.close()


def get_users():
    conn = get_db()

    rows = conn.execute(
        "SELECT user_id FROM users"
    ).fetchall()

    conn.close()

    return [row[0] for row in rows]


# =========================================================
# VIDEO STORAGE
# =========================================================

def save_video(file_id):
    conn = get_db()

    conn.execute("""
        INSERT OR REPLACE INTO settings
        (key, value)
        VALUES (?, ?)
    """, ("video_file_id", file_id))

    conn.commit()
    conn.close()


def get_video():
    conn = get_db()

    row = conn.execute("""
        SELECT value
        FROM settings
        WHERE key = ?
    """, ("video_file_id",)).fetchone()

    conn.close()

    return row[0] if row else None


# =========================================================
# MEMBERSHIP CHECK
# =========================================================

async def is_member(bot, user_id, channel_username):

    try:
        member = await bot.get_chat_member(
            chat_id=channel_username,
            user_id=user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as error:
        print(
            f"Membership error "
            f"{channel_username}: {error}"
        )
        return False


async def get_missing_channels(bot, user_id):

    missing = []

    for name, link, username in CHANNELS:

        joined = await is_member(
            bot,
            user_id,
            username
        )

        if not joined:
            missing.append(
                (name, link)
            )

    return missing


# =========================================================
# DYNAMIC CHANNEL BUTTONS
# =========================================================

async def create_keyboard(bot, user_id):

    missing = await get_missing_channels(
        bot,
        user_id
    )

    buttons = []

    for name, link in missing:

        buttons.append([
            InlineKeyboardButton(
                f"📢 {name}",
                url=link
            )
        ])

    if missing:

        buttons.append([
            InlineKeyboardButton(
                "🔄 Verify",
                callback_data="verify"
            )
        ])

    return InlineKeyboardMarkup(buttons), missing


# =========================================================
# SEND PROTECTED VIDEO
# =========================================================

async def send_saved_video(context, user_id):

    video_id = get_video()

    if not video_id:

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ Verification successful!\n\n"
                "⚠️ Admin ne abhi video upload nahi ki."
            )
        )

        return

    try:

        await context.bot.send_video(
            chat_id=user_id,
            video=video_id,
            caption="🎥 Enjoy!",
            protect_content=True
        )

    except Exception as error:

        print(
            f"Video send error "
            f"{user_id}: {error}"
        )


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    add_user(user_id)

    keyboard, missing = await create_keyboard(
        context.bot,
        user_id
    )

    # Already joined all channels
    if not missing:

        await update.message.reply_text(
            "✅ Verification successful!"
        )

        await send_saved_video(
            context,
            user_id
        )

        return

    await update.message.reply_text(
        "🔥 Welcome!\n\n"
        "Bot use karne ke liye "
        "remaining channels join karo.\n\n"
        "Join karne ke baad 🔄 Verify dabao.",
        reply_markup=keyboard
    )


# =========================================================
# VERIFY
# =========================================================

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    keyboard, missing = await create_keyboard(
        context.bot,
        user_id
    )

    # Some channels still missing
    if missing:

        channel_list = "\n".join(
            f"❌ {name}"
            for name, link in missing
        )

        try:

            await query.edit_message_text(
                "⚠️ Abhi ye channels pending hain:\n\n"
                f"{channel_list}\n\n"
                "Join karke 🔄 Verify dobara dabao.",
                reply_markup=keyboard
            )

        except Exception:
            pass

        return

    # Everything joined
    add_user(user_id)

    try:

        await query.edit_message_text(
            "✅ All channels verified!\n\n"
            "🎥 Video bhej raha hoon..."
        )

    except Exception:
        pass

    await send_saved_video(
        context,
        user_id
    )


# =========================================================
# ADMIN VIDEO AUTO-SAVE
# =========================================================

async def admin_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # Only admin can save/change video
    if user_id != ADMIN_ID:
        return

    if not update.message.video:
        return

    file_id = update.message.video.file_id

    save_video(file_id)

    await update.message.reply_text(
        "✅ Video successfully saved!\n\n"
        "Ab verified users ko latest video "
        "protected mode me milegi."
    )


# =========================================================
# BROADCAST
# =========================================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "❌ You are not authorized."
        )

        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "⚠️ Kisi message/video ko reply karo "
            "aur phir /broadcast bhejo."
        )

        return

    source = update.message.reply_to_message

    users = get_users()

    sent = 0
    failed = 0

    status = await update.message.reply_text(
        "📢 Broadcast started...\n\n"
        f"👥 Users: {len(users)}"
    )

    for user_id in users:

        try:

            # Protected copy
            await source.copy(
                chat_id=user_id,
                protect_content=True
            )

            sent += 1

            await asyncio.sleep(0.08)

        except Exception as error:

            failed += 1

            print(
                f"Broadcast failed "
                f"{user_id}: {error}"
            )

    await status.edit_text(
        "✅ Broadcast completed!\n\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# =========================================================
# ADMIN PANEL
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    users = get_users()

    video_exists = get_video() is not None

    await update.message.reply_text(
        "👑 ADMIN PANEL\n\n"
        f"👥 Registered users: {len(users)}\n"
        f"🎥 Saved video: "
        f"{'YES ✅' if video_exists else 'NO ❌'}\n\n"
        "🎥 Video bhejo → Auto-save\n\n"
        "📢 Broadcast:\n"
        "Message/video ko reply karo → /broadcast"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):

    print(
        "BOT ERROR:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("admin", admin)
    )

    app.add_handler(
        CommandHandler("broadcast", broadcast)
    )

    # Verify button
    app.add_handler(
        CallbackQueryHandler(
            verify,
            pattern="^verify$"
        )
    )

    # Admin video auto-save
    app.add_handler(
        MessageHandler(
            filters.VIDEO,
            admin_video
        )
    )

    # Error handler
    app.add_error_handler(
        error_handler
    )

    print("🤖 Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
