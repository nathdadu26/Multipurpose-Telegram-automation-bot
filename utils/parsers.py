import re

# https://t.me/c/<internal_id>/<message_id>  (private channel/supergroup link)
PRIVATE_LINK_RE = re.compile(r"t\.me/c/(\d+)/(\d+)")
# https://t.me/<username>/<message_id>  (public channel/group link)
PUBLIC_LINK_RE = re.compile(r"t\.me/([A-Za-z0-9_]+)/(\d+)")


def parse_message_ref(text: str):
    """Returns (channel_ref, message_id).
    channel_ref is either an int chat id (for /c/ links), a username string
    (for public links), or None if only a bare message ID was given.
    """
    text = text.strip()

    m = PRIVATE_LINK_RE.search(text)
    if m:
        internal_id = int(m.group(1))
        channel_id = int(f"-100{internal_id}")
        message_id = int(m.group(2))
        return channel_id, message_id

    m = PUBLIC_LINK_RE.search(text)
    if m:
        return m.group(1), int(m.group(2))

    if text.lstrip("-").isdigit():
        return None, int(text)

    raise ValueError("Couldn't parse a message link or ID from that text.")


def build_message_link(chat_id, message_id, username=None):
    """Build a t.me link to a specific message.
    Uses the public username form if available, otherwise the /c/ private
    form (only works for supergroups/channels, which use the -100 prefix —
    old-style basic groups have no stable public link format)."""
    if username:
        return f"https://t.me/{username}/{message_id}"
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        internal_id = chat_id_str[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return None
