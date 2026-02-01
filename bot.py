import time
import feedparser
import os
from telegram import Bot

TOKEN = "8437214679:AAHKtE6-UBzD4SLhyr-PGsrXlq0p2vxBNZ0"

CHANNEL_ID = "@LudmiCarsBot"
RSS_URL = "https://www.olx.ua/uk/rss/q-macbook-air/"

bot = Bot(token=TOKEN)

SEEN_FILE = "seen_links.txt"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        for link in seen:
            f.write(link + "\n")

seen_links = load_seen()

while True:
    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries:
        link = entry.link
        title = entry.title

        if link not in seen_links:
            message = f"{title}\n{link}"
            bot.send_message(chat_id=CHANNEL_ID, text=message)
            seen_links.add(link)
            save_seen(seen_links)

    time.sleep(60)
