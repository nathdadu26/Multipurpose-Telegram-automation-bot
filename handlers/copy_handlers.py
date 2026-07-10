import time
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

from handlers.admin_filter import admin_only
from utils.error_handler import safe_handler
from utils.parsers import parse_message_ref
from utils.formatting import format_progress
from utils.auto_delete import auto_delete
from keyboards.progress_kb import progress_keyboard
from database.repositories.job_repo import job_repo
from userbot.copy_engine import CopyJobRunner
from userbot.folder_manager import move_to_completed_folder
from userbot.client import userbot

logger = logging.getLogger("copy")

ASK_START, ASK_END = range(2)

# job_id -> CopyJobRunner, kept in-process so pause/cancel/restart buttons work
active_runners = {}


@admin_only
@safe_handler
async def copy_all_start(update, context):
    existing = await job_repo.get_active_job()
    if existing and existing["status"] == "running":
        await update.message.reply_text(
            f"⚠ A copy job is already running (ID: <code>{existing['_id']}</code>, "
            f"{existing['copied']} copied so far).\n\n"
            f"Use /cancel to stop it, or wait for it to finish, before starting a new one.",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🔗 Send the <b>starting</b> message link or ID.\n"
        "e.g. <code>https://t.me/c/3518263203/327994</code> or <code>327994</code>",
        parse_mode="HTML",
    )
    return ASK_START


@admin_only
@safe_handler
async def copy_all_ask_end(update, context):
    try:
        channel_ref, start_id = parse_message_ref(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return ASK_START

    context.user_data["copy_channel_ref"] = channel_ref
    context.user_data["copy_start_id"] = start_id
    await update.message.reply_text("🔗 Now send the <b>ending</b> message link or ID.", parse_mode="HTML")
    return ASK_END


@admin_only
@safe_handler
async def copy_all_run(update, context):
    try:
        channel_ref2, end_id = parse_message_ref(update.message.text)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return ASK_END

    channel_ref = context.user_data.get("copy_channel_ref") or channel_ref2
    start_id = context.user_data["copy_start_id"]

    if channel_ref is None:
        await update.message.reply_text(
            "❌ I need a channel reference (a full message link) at least once — a bare ID alone isn't enough."
        )
        return ConversationHandler.END

    try:
        source = await userbot.client.get_entity(channel_ref)
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't resolve that channel: {e}")
        return ConversationHandler.END

    source_id = source.id

    job_id = f"job_{int(time.time())}"
    await job_repo.create_job(job_id, source_id, start_id, end_id)

    progress_msg = await update.message.reply_text("🎬 Starting copy job...", reply_markup=progress_keyboard())
    context.chat_data["progress_message_id"] = progress_msg.message_id
    context.chat_data["progress_chat_id"] = progress_msg.chat_id
    context.chat_data["active_job_id"] = job_id
    context.chat_data["source_ref"] = source_id

    await start_job(context, job_id, source_id, source_id)
    return ConversationHandler.END


async def start_job(context, job_id, source_id, source_ref):
    state = {"last_update": 0.0, "start_time": time.time()}

    async def render_and_edit(current, end, copied, skipped, status, target_channel, keyboard=True):
        now = time.time()
        elapsed = max(1, now - state["start_time"])
        speed = f"{copied / (elapsed / 60):.1f} videos/min"
        remaining = max(0, end - current)
        eta_seconds = remaining * 10
        eta = f"{eta_seconds // 60}m {eta_seconds % 60}s"

        job = await job_repo.get(job_id)
        start_message = job["start_message"] if job else current

        text = format_progress(
            current, start_message, end, copied, skipped, speed, eta, target_channel, status,
        )
        try:
            await context.bot.edit_message_text(
                chat_id=context.chat_data["progress_chat_id"],
                message_id=context.chat_data["progress_message_id"],
                text=text, parse_mode="HTML",
                reply_markup=progress_keyboard() if keyboard else None,
            )
        except Exception:
            pass

    async def progress_cb(runner, current, end, copied, skipped, status="running"):
        now = time.time()
        if status == "running" and now - state["last_update"] < 10:
            return
        state["last_update"] = now
        job = await job_repo.get(job_id)
        target_channel = job.get("current_target_channel", "N/A") if job else "N/A"
        await render_and_edit(current, end, copied, skipped, status, target_channel)

    runner = CopyJobRunner(job_id, source_id, progress_callback=progress_cb)
    active_runners[job_id] = runner

    async def _run():
        result = await runner.run()
        active_runners.pop(job_id, None)
        chat_id = context.chat_data["progress_chat_id"]
        job = await job_repo.get(job_id)

        status_labels = {
            "completed": "🟢 Completed",
            "no_channel": "🔴 Stopped — no target channel",
            "cancelled": "🔴 Cancelled",
            "paused": "🟡 Paused",
        }
        label = status_labels.get(result, result)

        # Always finalize the progress message itself so it never sits
        # stuck at an in-progress percentage/status after the job ends.
        if job:
            await render_and_edit(
                job["current_message"], job["end_message"], job["copied"], job["skipped"],
                label, job.get("current_target_channel", "N/A"),
                keyboard=(result == "paused"),
            )

        if result == "completed":
            msg = await context.bot.send_message(chat_id, "✅ <b>Copy job completed!</b>", parse_mode="HTML")
            context.application.create_task(auto_delete(msg, 10))
            try:
                await move_to_completed_folder(source_ref)
            except Exception as e:
                logger.error("Couldn't move chat to 'Completed' folder: %s", e)
        elif result == "no_channel":
            await context.bot.send_message(chat_id, "❌ No available target channel. All channels are full.")
        elif result == "cancelled":
            await context.bot.send_message(chat_id, "🔴 Job cancelled.")

    context.application.create_task(_run())


@admin_only
@safe_handler
async def copy_button_handler(update, context):
    query = update.callback_query
    await query.answer()
    job_id = context.chat_data.get("active_job_id")
    if not job_id:
        return
    runner = active_runners.get(job_id)

    if query.data == "copy_cancel":
        if runner:
            runner.cancel()

    elif query.data == "copy_pause":
        if runner:
            runner.pause()
        else:
            job = await job_repo.get(job_id)
            if job and job["status"] == "paused":
                await job_repo.update(job_id, status="running")
                await start_job(context, job_id, job["source_channel_id"], job["source_channel_id"])

    elif query.data == "copy_restart":
        job = await job_repo.get(job_id)
        if runner:
            runner.cancel()
        await job_repo.update(job_id, current_message=job["start_message"], copied=0,
                               skipped=0, status="running")
        await start_job(context, job_id, job["source_channel_id"], job["source_channel_id"])


copy_all_conv = ConversationHandler(
    entry_points=[CommandHandler("copy_all", copy_all_start)],
    states={
        ASK_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, copy_all_ask_end)],
        ASK_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, copy_all_run)],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
)


@admin_only
@safe_handler
async def resume_cmd(update, context):
    job = await job_repo.get_active_job()
    if not job:
        await update.message.reply_text("Nothing to resume — no paused/running job found.")
        return

    context.chat_data["active_job_id"] = job["_id"]
    progress_msg = await update.message.reply_text("▶️ Resuming job...", reply_markup=progress_keyboard())
    context.chat_data["progress_message_id"] = progress_msg.message_id
    context.chat_data["progress_chat_id"] = progress_msg.chat_id
    await job_repo.update(job["_id"], status="running")
    await start_job(context, job["_id"], job["source_channel_id"], job["source_channel_id"])


@admin_only
@safe_handler
async def cancel_cmd(update, context):
    job_id = context.chat_data.get("active_job_id")
    if job_id and job_id in active_runners:
        active_runners[job_id].cancel()
        await update.message.reply_text("🔴 Cancelling job...")
    else:
        await update.message.reply_text("No active job in this chat.")
