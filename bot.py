import os
import json
import asyncio
import logging
from typing import Set

import aiohttp
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RSS_URL = os.getenv(
    "RSS_URL",
    "https://www.olx.pl/motoryzacja/samochody/?search%5Border%5D=created_at:desc&search%5Bfilter_float_price:to%5D=7000&search%5Bfilter_float_year:from%5D=2000&format=rss",
).strip()

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
SEEN_FILE = "seen.json"


def load_seen() -> Set[str]:
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(map(str, data))
        return set()
    except Exception:
        return set()


def save_seen(seen: Set[str]) -> None:
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f)
    except Exception:
        pass


def entry_id(e) -> str:
    return str(getattr(e, "id", "") or e.get("id") or e.get("link") or e.get("title") or "")


async def fetch_rss_text() -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(RSS_URL) as r:
            r.raise_for_status()
            return await r.text()


async def rss_tick(app: Application) -> None:
    chat_id = app.bot_data.get("chat_id")
    if not chat_id:
        return

    seen: Set[str] = app.bot_data.setdefault("seen", load_seen())

    text = await fetch_rss_text()
    feed = feedparser.parse(text)

    new_entries = []
    for e in feed.entries:
        eid = entry_id(e)
        if eid and eid not in seen:
            new_entries.append((eid, e))

    if not new_entries:
        return

    new_entries.reverse()

    for eid, e in new_entries:
        title = e.get("title", "").strip()
        link = e.get("link", "").strip()
        msg = f"{title}\n{link}".strip()

        if msg:
            await app.bot.send_message(chat_id=chat_id, text=msg)

        seen.add(eid)
        await asyncio.sleep(0.3)

    save_seen(seen)


async def rss_loop(app: Application) -> None:
    while True:
        try:
            await rss_tick(app)
        except Exception:
            log.exception("rss_loop error")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bot running")


async def settarget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = update.effective_chat.id
    context.application.bot_data["chat_id"] = cid
    await update.message.reply_text(f"Target set: {cid}")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = context.application.bot_data.get("chat_id")
    await update.message.reply_text(f"Target: {cid}\nInterval: {CHECK_INTERVAL_SECONDS}s\nRSS_URL: {RSS_URL}")


async def testsend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = context.application.bot_data.get("chat_id")
    if not cid:
        await update.message.reply_text("Target is not set")
        return
    await context.application.bot.send_message(chat_id=cid, text="Test")


async def post_init(app: Application) -> None:
    app.bot_data["seen"] = load_seen()
    asyncio.create_task(rss_loop(app))


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("settarget", settarget_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
