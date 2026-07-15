import asyncio
import logging

from telethon.errors import FloodWaitError, RPCError, ChatWriteForbiddenError

from userbot.client import userbot

logger = logging.getLogger("promo_poster")

_ENTITY_ERROR_HINTS = ("cannot find any entity", "no user has", "could not find the input entity")


async def repost_via_userbot(target_id, source_channel_id, message_id, retries=2, username=None):
    """Fetch the staged ad message from the ad channel and resend it — via
    the userbot account, not the Bot API — into target_id.

    This is what makes promotion posting work in groups where the *userbot*
    account is a member but the *bot* account is not (the Bot API's
    copy_message would otherwise fail with "Chat not found" in that case).

    Resends without a forward tag, matching the "always copy, never forward"
    rule used elsewhere in the project.
    """
    client = userbot.client
    refreshed_once = False

    for attempt in range(retries + 1):
        try:
            message = await client.get_messages(source_channel_id, ids=message_id)
            if message is None:
                raise ValueError("Source ad message not found (was it deleted from the ad channel?)")

            target = target_id
            if message.media:
                sent = await client.send_file(target, message.media, caption=message.text or "")
            else:
                sent = await client.send_message(target, message.text or "")
            return sent

        except FloodWaitError as e:
            logger.warning("FloodWait %ss while reposting to %s", e.seconds, target_id)
            await asyncio.sleep(e.seconds + 1)
            continue

        except ChatWriteForbiddenError:
            raise RuntimeError("Userbot account cannot write in this group (banned/read-only/removed).")

        except (ValueError, RPCError) as e:
            msg = str(e).lower()
            is_entity_error = any(hint in msg for hint in _ENTITY_ERROR_HINTS)

            # The userbot hasn't cached this chat's access hash yet (e.g. it
            # was added via a bot-forwarded message before a dialog refresh).
            # Refresh the dialog cache once, then try resolving by username
            # if we have one stored, before giving up.
            if is_entity_error and not refreshed_once:
                refreshed_once = True
                logger.info("Entity not cached for %s, refreshing dialogs...", target_id)
                await userbot.refresh_dialogs()
                if username:
                    try:
                        target_id = await client.get_entity(f"@{username}")
                    except Exception:
                        pass
                continue

            if attempt < retries:
                logger.warning("RPC error reposting to %s (attempt %s/%s): %s",
                               target_id, attempt + 1, retries, e)
                await asyncio.sleep(2)
                continue
            raise

    raise RuntimeError(
        "Could not resolve or write to this chat. Make sure the userbot account "
        "is a member of the group, then remove and re-add it with /set_target."
    )
