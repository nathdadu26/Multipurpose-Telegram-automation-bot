"""
Run this once locally to generate a Telethon STRING_SESSION for your userbot
account. Never share the resulting string — it grants full account access.

Usage:
    python scripts/generate_session.py
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = int(input("API_ID: ").strip())
    api_hash = input("API_HASH: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()
        print("\nYour STRING_SESSION (put this in .env):\n")
        print(session_string)

if __name__ == "__main__":
    asyncio.run(main())
