import time
import feedparser
import os
import threading

from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== НАЛАШТУВАННЯ =====
TOKEN = "8437214679:AAHy_IhJaVqPiCz5Gylt4D2E0UBLapneqAQ"
CHANNEL_ID = "@LudmiCarsBot"
RSS_URL = "https://www.olx.ua/uk/rss/q-macbook-air/"
SEEN_FILE = "seen_links.txt"

bot = Bot(token=TOKEN)

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я живий 🟢")

# ===== SEEN LINKS =====
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        for link in seen:
            f.write(link + "\n")

# ===== RSS WORKER =====
def rss_worker():
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

# ===== MAIN =====
if __name__ == "__main__":
    threading.Thread(target=rss_worker, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
