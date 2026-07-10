# Multipurpose Telegram Automation Bot

Telethon userbot + python-telegram-bot admin bot, MongoDB-backed, built for Railway deployment.

## Architecture

```
config/       env-based settings
database/     Mongo connection + repository pattern (channels, groups, jobs, promotion, settings)
models/       typed dataclasses mirroring the Mongo documents
userbot/      Telethon client, copy engine, chat-folder manager
handlers/     python-telegram-bot command/conversation/callback handlers
keyboards/    inline keyboard builders
scheduler/    APScheduler hourly promotion reposting
utils/        logging, parsing, formatting, auto-delete, error handling
main.py       wires everything together and starts polling
```

## 1. Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Generate your userbot STRING_SESSION

```bash
python scripts/generate_session.py
```

Get `API_ID` / `API_HASH` from https://my.telegram.org, then follow the prompts.
Paste the resulting string into `STRING_SESSION` in `.env`. **Never share this string** — it's full account access.

### Fill in `.env`

```
BOT_TOKEN=          # from @BotFather
API_ID=
API_HASH=
STRING_SESSION=
ADMIN_IDS=          # comma-separated Telegram user IDs (e.g. 123456,789012)
AD_CHANNEL_ID=      # a private channel the bot/userbot can post to, used to stage ads
MONGO_URI=          # MongoDB Atlas connection string (see below)
MONGO_DB_NAME=telegram_bot
UPLOAD_DELAY=10
GROUP_POST_DELAY=60
PROMOTION_INTERVAL=3600
CHANNEL_LIMIT=2000
LOG_LEVEL=INFO
```

### MongoDB

Easiest path: create a free cluster at https://cloud.mongodb.com (Atlas), add a database user,
whitelist `0.0.0.0/0` (Railway's egress IPs aren't static), and copy the `mongodb+srv://...` URI into `MONGO_URI`.

### Run locally

```bash
python main.py
```

## 2. Deploying to Railway

1. Push this project to a GitHub repo.
2. In Railway: **New Project → Deploy from GitHub repo**.
3. Add all the `.env` variables under the service's **Variables** tab (Railway does not read `.env` files from the repo — set them in the dashboard).
4. Railway will detect `railway.json` / `Procfile` and run `python main.py`. No exposed port is needed since this is a polling worker, not a web server — deploy it as a **Worker**, not a web service, when prompted.
5. Watch the deploy logs for `Startup complete — bot is online`.

Since the bot uses long-polling (not webhooks), Railway's ephemeral filesystem is fine — no persistent disk needed, all state lives in MongoDB.

## 3. Feature notes / commands

All commands are admin-only (`ADMIN_IDS`); every other user is silently ignored. Multiple admins are supported — set `ADMIN_IDS` as a comma-separated list. The legacy `ADMIN_ID` (single value) is also accepted for backward compatibility.

- `/add_channel` — forward a message from a target channel to register it (repeat for unlimited channels). Capacity is 2000 videos/channel (`CHANNEL_LIMIT`); the engine auto-advances to the next channel with room.
- `/copy_all` — send a starting then ending message link/ID (e.g. `https://t.me/c/3518263203/327994` or a bare `327994`). Only actual video files are copied (photos/audio/voice/gifs/documents/text/stickers/polls are skipped); captions are stripped; messages are always copied, never forwarded. A single progress message is edited in place every ~10s with a progress bar, ETA, speed, and Pause/Restart/Cancel buttons. On completion the source chat is auto-added to a Telegram **Completed** chat folder via Telethon's dialog-filter API.
- Sending a **video directly in the bot's DM** (no command) uploads it straight to the current open channel and deletes the original DM.
- `/ad_promotion` — stage a promo message (text/photo/video/animation) into `AD_CHANNEL_ID`; `/set_target` registers promotion groups (forward a message or send a link); the APScheduler job reposts the staged message (never the original) to every group sequentially, `GROUP_POST_DELAY` seconds apart, once per `PROMOTION_INTERVAL`.
- `/status`, `/stats`, `/logs`, `/channels`, `/groups`, `/resume`, `/cancel` round out visibility/control.

## 4. Resumability

Copy-job progress (`current_message`, `copied`, `skipped`, `status`) is written to MongoDB after every single message, not just on pause. If the process is killed or the VPS/Railway instance restarts mid-job, run `/resume` after the bot comes back up and it will continue from the last saved `current_message` rather than restarting. True auto-resume-on-boot (without the admin typing `/resume`) isn't wired into `post_init` by default — add a call to the same logic used in `resume_cmd` there if you want it to resume with zero interaction.

## 5. Honest scope notes

This is a full working implementation of every feature requested, but a few things are worth knowing before you run it 24/7 unattended:

- **Chat-folder API (`userbot/folder_manager.py`)** uses Telethon's `DialogFilter`/`UpdateDialogFilterRequest`. Telegram has changed this API's exact shape across layers (e.g. `title` becoming a `TextWithEntities`-like object in newer clients) — if `move_to_completed_folder` throws on your Telethon version, check Telethon's changelog for `DialogFilter` and adjust the `title=` argument accordingly.
- **"Skip missing IDs"** is treated as skip-and-count; genuinely deleted/inaccessible messages and non-video messages are both counted as "skipped" (the spec didn't distinguish the two, so they share one counter — split this in `job_repo`/`copy_engine.py` if you want separate counts).
- **Speed/ETA** in the progress bar are computed from the fixed `UPLOAD_DELAY`, not measured network throughput — fine for a delay-driven pipeline like this one, but it's an estimate, not a live measurement.
- **FloodWait handling** retries with the exact wait Telegram tells us to use, for both the copy engine and general handlers; RPC errors that aren't flood-related are logged and the message is skipped rather than retried indefinitely, to avoid an infinite loop on a genuinely broken message.
- Test `/copy_all` on a small range (5–10 messages) first — copying real production ranges before confirming your channel permissions, `AD_CHANNEL_ID`, and Mongo connection all work correctly will save you a slow debugging cycle at 10s/video.

## 6. Command registration

`post_init` in `main.py` fetches current bot commands and only calls `set_my_commands` if they differ from the desired list — satisfying "if commands already exist, skip them" without extra state.
