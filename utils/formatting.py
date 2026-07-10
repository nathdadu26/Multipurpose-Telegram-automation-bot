def progress_bar(percent: float, length: int = 10) -> str:
    percent = max(0, min(100, percent))
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


def format_progress(current, start, end, copied, skipped, speed, eta, target_channel, status):
    total = max(1, end - start + 1)
    done = max(0, current - start)
    percent = min(100, int(done / total * 100))
    bar = progress_bar(percent)
    remaining = max(0, end - current)

    return (
        "📊 <b>Copy Progress</b>\n\n"
        f"<code>{bar}</code> {percent}%\n\n"
        f"🎬 Copied: <b>{copied}</b>\n"
        f"⏭ Skipped: <b>{skipped}</b>\n"
        f"📍 Remaining: <b>{remaining}</b>\n"
        f"🆔 Current Message ID: <code>{current}</code>\n"
        f"📁 Target Channel: <code>{target_channel}</code>\n"
        f"⏳ ETA: <b>{eta}</b>\n"
        f"⚡ Speed: <b>{speed}</b>\n"
        f"🟢 Status: <b>{status}</b>"
    )
