import os
import time
import requests
import feedparser

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== НАЛАШТУВАННЯ ==================
# Токен краще тримати в Render → Environment → BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# OLX Polska: samochody, prywatne, do 5000 zł, od najnowszych + RSS
RSS_URL = "https://www.olx.pl/motoryzacja/samochody/?search%5Bfilter_float_price%3Ato%5D=5000&search%5Bprivate_business%5D=private&search%5Border%5D=created_at:desc&rss=1"

SEEN_FILE = "seen_links_pl_seen.txt"
CHAT_FILE = "target_chat_id.txt"

CHECK_INTERVAL_SECONDS = 60
TIMEOUT_SECONDS = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OLX-RSS-Telegram-Bot/1.0)"
}


# ================== ДОПОМІЖНІ ФУНКЦІЇ ==================
def load_seen() -> set[str]:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_seen(seen: set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for link in sorted(seen):
            f.write(link + "\n")


def save_chat_id(chat_id: int) -> None:
    with open(CHAT_FILE, "w", encoding="utf-8") as f:
        f.write(str(chat_id))


def load_chat_id() -> int | None:
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except:
            return None
    return None


def fetch_feed(url: str):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return feedparser.parse(r.text)


def link_alive(url: str) -> bool:
    # OLX іноді віддає “мертві” лінки, фільтруємо 404/редіректи
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS, allow_redirects=True)
        return r.status_code == 200
    except:
        return False


# ================== КОМАНДИ ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    await update.message.reply_text("Я живий 🟢\nОк, буду скидати нові оголошення сюди.")


# ================== JOB: ПЕРЕВІРКА RSS ==================
async def rss_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = load_chat_id()
    if chat_id is None:
        # Нема куди слати, поки користувач не написав /start
        print("⏳ Чекаю /start, щоб запам’ятати chat_id…")
        return

    seen = load_seen()

    try:
        print("🔎 Перевіряю RSS…")
        feed = fetch_feed(RSS_URL)
        print("📦 Знайдено items:", len(feed.entries))

        posted = 0
        for entry in feed.entries:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", "Нове оголошення")

            if not link:
                continue

            if link in seen:
                continue

            # пропускаємо мертві лінки, але все одно заносимо в seen, щоб не мучитись
            if link_alive(link):
                text = f"🚗 {title}\n{link}"
                await context.bot.send_message(chat_id=chat_id, text=text)
                posted += 1
            else:
                print("⚠️ Мертвий лінк (пропущено):", link)

            seen.add(link)

        if posted:
            print("✅ Надіслано нових:", posted)
        else:
            print("— Нічого нового")

        save_seen(seen)

    except Exception as e:
        print("❌ Помилка при перевірці RSS:", repr(e))


# ================== MAIN ==================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("Нема BOT_TOKEN. Додай його в Render → Environment (ключ BOT_TOKEN).")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))

    # кожні 60 секунд перевіряємо RSS
    app.job_queue.run_repeating(rss_job, interval=CHECK_INTERVAL_SECONDS, first=5)

    print("✅ Bot started. Waiting for /start…")
    app.run_polling()
    if __name__ == "__main__":
    main()
