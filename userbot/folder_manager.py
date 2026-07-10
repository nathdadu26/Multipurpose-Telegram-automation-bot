import logging
from telethon.tl import functions, types
from userbot.client import userbot

logger = logging.getLogger("userbot")

FOLDER_TITLE = "Completed"


async def move_to_completed_folder(peer):
    """Move the given chat into a Telegram Chat Folder named 'Completed',
    creating the folder if it doesn't already exist."""
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
            if title_text == FOLDER_TITLE:
                target_filter = f
                break

    if target_filter is None:
        existing_ids = [f.id for f in folder_list if hasattr(f, "id")]
        new_id = (max(existing_ids) + 1) if existing_ids else 2
        target_filter = types.DialogFilter(
            id=new_id,
            title=FOLDER_TITLE,
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
        logger.info("Created 'Completed' chat folder")
    else:
        already_in = any(
            getattr(p, "channel_id", None) == getattr(input_peer, "channel_id", object())
            for p in target_filter.include_peers
        )
        if not already_in:
            target_filter.include_peers.append(input_peer)
            await client(functions.messages.UpdateDialogFilterRequest(id=target_filter.id, filter=target_filter))
        logger.info("Moved source chat into 'Completed' folder")
