from telegram.ext import ContextTypes
from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from database.repositories.channel_repo import channel_repo
from database.repositories.group_repo import group_repo
from database.repositories.job_repo import job_repo


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
        await update.message.reply_text("🔴 No active job.")
        return
    await update.message.reply_text(
        f"🟢 <b>Job Status</b>\n\n"
        f"ID: <code>{job['_id']}</code>\n"
        f"Status: {job['status']}\n"
        f"Progress: {job['current_message']}/{job['end_message']}\n"
        f"Copied: {job['copied']} | Skipped: {job['skipped']}",
        parse_mode="HTML",
    )


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
