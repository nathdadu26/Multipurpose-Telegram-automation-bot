import time
from telegram.ext import ContextTypes
from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from utils.formatting import format_status_progress
from database.repositories.channel_repo import channel_repo
from database.repositories.group_repo import group_repo
from database.repositories.job_repo import job_repo
from config.settings import settings
from userbot.client import userbot
from scheduler.promotion_scheduler import get_promotion_status


@admin_only
@safe_handler
async def start_cmd(update, context):
    await update.message.reply_text("🟢 <b>Bot Online</b>\n\nUse /help to see all commands.", parse_mode="HTML")


@admin_only
@safe_handler
async def help_cmd(update, context):
    text = (
        "📖 <b>Commands</b>\n\n"
        "/copy_all – copy videos between message range\n"
        "/add_channel – add a target channel\n"
        "/remove_channel &lt;id&gt; – remove a channel\n"
        "/channels – list target channels\n"
        "/ad_promotion – set promotional message\n"
        "/set_target – add promotion group\n"
        "/groups – list promotion groups\n"
        "/remove_group &lt;id&gt; – remove a promotion group\n"
        "/resume – resume paused copy job\n"
        "/cancel – cancel current job\n"
        "/status – current job status\n"
        "/stats – overall stats\n"
        "/logs – recent logs\n\n"
        "Tip: sending a video directly in this DM (no command) uploads it "
        "straight to the current target channel."
    )
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
@safe_handler
async def status_cmd(update, context):
    job = await job_repo.get_active_job()

    if not job:
        text = "🔴 No active copy job."
    else:
        # Derive elapsed time from the job's creation timestamp (embedded in
        # its ID) so /status reflects the real running process from the DB —
        # not just whatever chat happened to start it.
        try:
            created_ts = int(job["_id"].rsplit("_", 1)[1])
        except (ValueError, IndexError):
            created_ts = int(time.time())
        elapsed = max(1, time.time() - created_ts)
        speed_val = job["copied"] / (elapsed / 60)
        speed = f"{speed_val:.1f} videos/min"

        remaining = max(0, job["end_message"] - job["current_message"])
        eta_seconds = int(remaining * settings.upload_delay)
        eta = f"{eta_seconds // 60}m {eta_seconds % 60}s"

        try:
            src_entity = await userbot.client.get_entity(job["source_channel_id"])
            source_name = getattr(src_entity, "title", None) or str(job["source_channel_id"])
        except Exception:
            source_name = str(job["source_channel_id"])

        target_id = job.get("current_target_channel")
        target_name = "N/A"
        if target_id:
            target_doc = await channel_repo.get(target_id)
            target_name = target_doc["title"] if target_doc else str(target_id)

        text = format_status_progress(
            source_name, target_name,
            job["current_message"], job["start_message"], job["end_message"],
            job["copied"], job["skipped"], speed, eta,
            job.get("current_target_channel", "N/A"), job["status"],
        )

    promo_status = get_promotion_status()
    if promo_status.get("running"):
        text += (
            f"\n\n📢 <b>Promotion Posting (live)</b>\n"
            f"Group {promo_status['index']}/{promo_status['total']} — {promo_status['current_group']}"
        )

    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
@safe_handler
async def stats_cmd(update, context):
    channels = await channel_repo.list_all()
    groups = await group_repo.list_all()
    total_uploaded = sum(c.get("total_uploaded", 0) for c in channels)
    await update.message.reply_text(
        f"📊 <b>Stats</b>\n\n"
        f"Channels: {len(channels)}\n"
        f"Groups: {len(groups)}\n"
        f"Total Videos Uploaded: {total_uploaded}",
        parse_mode="HTML",
    )


@admin_only
@safe_handler
async def logs_cmd(update, context):
    try:
        with open("bot.log", "r", encoding="utf-8") as f:
            lines = f.readlines()[-40:]
        text = "".join(lines) or "No logs yet."
    except FileNotFoundError:
        text = "No logs yet."
    await update.message.reply_text(f"<pre>{text[-3500:]}</pre>", parse_mode="HTML")
