import os
import json
import asyncio
import logging
from typing import Optional, Set, List, Tuple

import aiohttp
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

RSS_URL = os.getenv(
    "RSS_URL",
    "https://www.olx.pl/motoryzacja/samochody/lodzkie/?search%5Bfilter_float_price:to%5D=7000&search%5Bfilter_float_year:from%5D=2000&format=rss",
)

CHECK_INTERVAL_SECONDS = 300
SEEN_FILE = "seen.json"


def load_seen() -> Set[str]:
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen: Set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)


def entry_id(entry: dict) -> str:
    return entry.get("link", entry.get("id", entry.get("title", "")))


async def fetch_rss():
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(RSS_URL) as r:
            r.raise_for_status()
            return await r.text()


async def rss_tick(app: Application):
    chat_id = app.bot_data.get("chat_id")
    if not chat_id:
        return

    seen = app.bot_data.setdefault("seen", load_seen())

    text = await fetch_rss()
    feed = feedparser.parse(text)

    new = []
    for e in feed.entries:
        eid = entry_id(e)
        if eid not in seen:
            new.append((eid, e))

    new.reverse()

    for eid, e in new:
        msg = f"{e.get('title','')}\n{e.get('link','')}"
        await app.bot.send_message(chat_id=chat_id, text=msg)
        seen.add(eid)
        await asyncio.sleep(0.3)

    save_seen(seen)


async def rss_loop(app: Application):
    while True:
        try:
            await rss_tick(app)
        except Exception:
            logging.exception("rss error")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot running")


async def settarget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    context.application.bot_data["chat_id"] = cid
    await update.message.reply_text(f"Target set: {cid}")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = context.application.bot_data.get("chat_id")
    await update.message.reply_text(f"Target: {cid}\nInterval: 300s")


async def testsend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = context.application.bot_data.get("chat_id")
    if cid:
        await context.application.bot.send_message(chat_id=cid, text="Test")


async def post_init(app: Application):
    app.bot_data["seen"] = load_seen()
    asyncio.create_task(rss_loop(app))


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("settarget", settarget_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
