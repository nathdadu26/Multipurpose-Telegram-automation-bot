import asyncio
import logging
import time

from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, DocumentAttributeAnimated

from userbot.client import userbot
from database.repositories.channel_repo import channel_repo
from database.repositories.job_repo import job_repo
from database.repositories.media_repo import media_repo
from config.settings import settings

logger = logging.getLogger("copy_engine")

# Telegram encodes GIFs as silent, muted mp4 "video" documents, which is why
# they otherwise look identical to a real video to Telethon. Two extra
# signals catch that case: the DocumentAttributeAnimated marker Telegram
# attaches to actual GIFs, and a size floor — a real video is almost never
# under ~1MB, while converted GIFs almost always are.
MIN_VIDEO_SIZE_BYTES = 1_000_000  # 1MB


def is_video_message(message) -> bool:
    """Only real video files count. Photos, audio, voice, gifs, documents,
    text, stickers and polls are all excluded."""
    if not message or not message.media:
        return False
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc is None:
            return False

        if any(isinstance(a, DocumentAttributeAnimated) for a in doc.attributes):
            return False  # definitely a GIF, not a video

        if any(isinstance(a, DocumentAttributeVideo) for a in doc.attributes):
            if getattr(message.media, "voice", False):
                return False
            if any(getattr(a, "round_message", False) for a in doc.attributes
                   if isinstance(a, DocumentAttributeVideo)):
                return False
            if doc.size < MIN_VIDEO_SIZE_BYTES:
                return False  # too small to plausibly be a real video
            return True

        if doc.mime_type and doc.mime_type.startswith("video/") and doc.mime_type != "video/mp4-gif":
            if doc.size < MIN_VIDEO_SIZE_BYTES:
                return False
            return True
    return False


class CopyJobRunner:
    def __init__(self, job_id, source_channel_id, progress_callback=None):
        self.job_id = job_id
        self.source_channel_id = source_channel_id
        self.progress_callback = progress_callback
        self._cancel = False
        self._pause = False
        self.start_time = time.time()

    def cancel(self):
        self._cancel = True

    def pause(self):
        self._pause = True

    async def run(self):
        client = userbot.client
        job = await job_repo.get(self.job_id)
        current = job["current_message"]
        end = job["end_message"]
        copied = job["copied"]
        skipped = job["skipped"]

        source = await client.get_entity(self.source_channel_id)
        next_msg = await client.get_messages(source, ids=current)

        while current <= end:
            if self._cancel:
                await job_repo.update(self.job_id, status="cancelled", current_message=current,
                                       copied=copied, skipped=skipped)
                return "cancelled"
            if self._pause:
                await job_repo.update(self.job_id, status="paused", current_message=current,
                                       copied=copied, skipped=skipped)
                return "paused"

            message = next_msg

            # prefetch next message while we process/wait on this one
            fetch_task = None
            if current + 1 <= end:
                fetch_task = asyncio.create_task(client.get_messages(source, ids=current + 1))

            if message is None or not is_video_message(message):
                skipped += 1
            else:
                doc = message.media.document
                is_duplicate = await media_repo.exists(doc.id)

                if is_duplicate:
                    logger.info("Skipped duplicate video at message %s (doc_id=%s, already copied before)",
                                current, doc.id)
                    skipped += 1
                else:
                    target = await channel_repo.get_available_channel(settings.channel_limit)
                    if not target:
                        await job_repo.update(self.job_id, status="stopped_no_channel",
                                               current_message=current, copied=copied, skipped=skipped)
                        if self.progress_callback:
                            await self.progress_callback(
                                self, current, end, copied, skipped,
                                status="Stopped: no available target channel"
                            )
                        if fetch_task:
                            fetch_task.cancel()
                        return "no_channel"

                    sent_ok = False
                    for attempt in range(3):
                        try:
                            await client.send_file(target["_id"], message.media, caption="")
                            sent_ok = True
                            break
                        except FloodWaitError as e:
                            logger.warning("FloodWait %ss on message %s", e.seconds, current)
                            await asyncio.sleep(e.seconds + 1)
                        except RPCError as e:
                            logger.error("RPC error copying message %s: %s", current, e)
                            break
                        except Exception as e:
                            logger.error("Unexpected error copying message %s: %s", current, e)
                            break

                    if sent_ok:
                        await channel_repo.increment_upload(target["_id"])
                        await job_repo.update(self.job_id, current_target_channel=target["_id"])
                        await media_repo.record(doc.id, size=doc.size, source_message_id=current)
                        copied += 1
                    else:
                        skipped += 1

            await job_repo.update(self.job_id, current_message=current, copied=copied, skipped=skipped)

            if self.progress_callback:
                await self.progress_callback(self, current, end, copied, skipped, status="running")

            if fetch_task:
                next_msg = await fetch_task

            current += 1
            if current <= end:
                await asyncio.sleep(settings.upload_delay)

        await job_repo.update(self.job_id, status="completed", current_message=end,
                               copied=copied, skipped=skipped)
        return "completed"
