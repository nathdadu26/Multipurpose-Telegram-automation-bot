from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def progress_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause/Resume", callback_data="copy_pause"),
            InlineKeyboardButton("🔄 Restart", callback_data="copy_restart"),
            InlineKeyboardButton("❌ Cancel", callback_data="copy_cancel"),
        ]
    ])
