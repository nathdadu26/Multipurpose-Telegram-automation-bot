import logging
from telethon.tl import functions, types
from userbot.client import userbot

logger = logging.getLogger("userbot")

COMPLETED_FOLDER_TITLE = "Completed"
POSTS_GROUPS_FOLDER_TITLE = "Posts Groups"
TARGET_CHANNELS_FOLDER_TITLE = "Target Channels"


async def add_chat_to_folder(peer, folder_title: str):
    """Add the given chat into a Telegram Chat Folder with the given title,
    creating the folder if it doesn't already exist. Safe to call
    repeatedly — a chat already in the folder is left alone."""
    client = userbot.client
    entity = await client.get_entity(peer)
    input_peer = await client.get_input_entity(entity)

    result = await client(functions.messages.GetDialogFiltersRequest())
    folder_list = getattr(result, "filters", result)

    target_filter = None
    for f in folder_list:
        if isinstance(f, types.DialogFilter):
            title = f.title
            title_text = title.text if hasattr(title, "text") else title
            if title_text == folder_title:
                target_filter = f
                break

    if target_filter is None:
        existing_ids = [f.id for f in folder_list if hasattr(f, "id")]
        new_id = (max(existing_ids) + 1) if existing_ids else 2
        target_filter = types.DialogFilter(
            id=new_id,
            title=folder_title,
            pinned_peers=[],
            include_peers=[input_peer],
            exclude_peers=[],
            contacts=False,
            non_contacts=False,
            groups=False,
            broadcasts=False,
            bots=False,
            exclude_muted=False,
            exclude_read=False,
            exclude_archived=False,
        )
        await client(functions.messages.UpdateDialogFilterRequest(id=new_id, filter=target_filter))
        logger.info("Created '%s' chat folder", folder_title)
    else:
        already_in = any(
            getattr(p, "channel_id", None) == getattr(input_peer, "channel_id", object())
            for p in target_filter.include_peers
        )
        if not already_in:
            target_filter.include_peers.append(input_peer)
            await client(functions.messages.UpdateDialogFilterRequest(id=target_filter.id, filter=target_filter))
        logger.info("Added chat into '%s' folder", folder_title)


async def move_to_completed_folder(peer):
    """Move the given chat into the 'Completed' chat folder (used after a
    /copy_all job finishes)."""
    await add_chat_to_folder(peer, COMPLETED_FOLDER_TITLE)


async def add_to_posted_groups_folder(peer):
    """Add the given chat into the 'Posts Groups' chat folder (used when a
    group is registered via /set_target)."""
    await add_chat_to_folder(peer, POSTS_GROUPS_FOLDER_TITLE)


async def add_to_target_channels_folder(peer):
    """Add the given chat into the 'Target Channels' chat folder (used when
    a channel is registered via /add_channel)."""
    await add_chat_to_folder(peer, TARGET_CHANNELS_FOLDER_TITLE)
