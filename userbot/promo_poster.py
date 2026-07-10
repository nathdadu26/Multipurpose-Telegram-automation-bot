import asyncio
import logging

from telethon.errors import FloodWaitError, RPCError, ChatWriteForbiddenError

from userbot.client import userbot

logger = logging.getLogger("promo_poster")


async def repost_via_userbot(target_id, source_channel_id, message_id, retries=2):
    """Fetch the staged ad message from the ad channel and resend it — via
    the userbot account, not the Bot API — into target_id.

    This is what makes promotion posting work in groups where the *userbot*
    account is a member but the *bot* account is not (the Bot API's
    copy_message would otherwise fail with "Chat not found" in that case).

    Resends without a forward tag, matching the "always copy, never forward"
    rule used elsewhere in the project.
    """
    client = userbot.client

    for attempt in range(retries + 1):
        try:
            message = await client.get_messages(source_channel_id, ids=message_id)
            if message is None:
                raise ValueError("Source ad message not found (was it deleted from the ad channel?)")

            if message.media:
                await client.send_file(target_id, message.media, caption=message.text or "")
            else:
                await client.send_message(target_id, message.text or "")
            return

        except FloodWaitError as e:
            logger.warning("FloodWait %ss while reposting to %s", e.seconds, target_id)
            await asyncio.sleep(e.seconds + 1)
            continue

        except ChatWriteForbiddenError:
            raise RuntimeError("Userbot account cannot write in this group (banned/read-only/removed).")

        except RPCError as e:
            if attempt < retries:
                logger.warning("RPC error reposting to %s (attempt %s/%s): %s",
                               target_id, attempt + 1, retries, e)
                await asyncio.sleep(2)
                continue
            raise

    raise RuntimeError("Failed to repost after retries (flood wait loop).")
