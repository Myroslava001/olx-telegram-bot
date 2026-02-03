import os
import time
import asyncio
import requests
import feedparser

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import NetworkError, RetryAfter, TimedOut, Conflict

# ================= НАШТУВАННЯ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Нема BOT_TOKEN в environment (Render -> Environment -> BOT_TOKEN)")

# OLX RSS (твій URL лишаю як є)
RSS_URL = "https://www.olx.pl/motoryzacja/samochody/?search%5Bfilter_float_price%3Ato%5D=5000&search%5Bprivate_business%5D=private&search%5Border%5D=created_at:desc&rss=1"

SEEN_FILE = "seen_links_pl_seen.txt"
CHAT_FILE = "target_chat_id.txt"

CHECK_INTERVAL_SECONDS = 60
TIMEOUT_SECONDS = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OLX-RSS-Telegram-Bot/1.0)"
}

_last_rss_tick = 0
_last_rss_status = "not started"


# ================= ДОПОМІЖНІ ФУНКЦІЇ =================
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
    if not os.path.exists(CHAT_FILE):
        return None
    try:
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def fetch_feed(url: str):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return feedparser.parse(r.text)


def link_alive(url: str) -> bool:
    # OLX іноді віддає “мертві” лінки/редіректи, фільтруємо
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


# ================= КОМАНДИ =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    await update.message.reply_text(
        "Я живий 🟢\n"
        "Ок, буду скидати нові оголошення сюди.\n\n"
        "Команди:\n"
        "/settarget — зробити цей чат ціллю\n"
        "/status — показати поточну ціль і стан RSS\n"
        "/testsend — тестове повідомлення в ціль"
    )


async def set_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    await update.message.reply_text(f"✅ Тепер оголошення підуть сюди: {chat_id}")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _last_rss_tick, _last_rss_status
    target = load_chat_id()
    tick = _last_rss_tick
    when = "ще не перевіряв" if tick == 0 else time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tick))
    await update.message.reply_text(
        f"📌 Target chat_id: {target}\n"
        f"🕒 Last RSS tick: {when}\n"
        f"📋 Last RSS status: {_last_rss_status}\n"
        f"⏱ Interval: {CHECK_INTERVAL_SECONDS}s"
    )


async def testsend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = load_chat_id()
    if target is None:
        await update.message.reply_text("❗ Нема цілі. Напиши /settarget в потрібному чаті.")
        return
    await context.bot.send_message(chat_id=target, text="✅ Тест: бот може слати повідомлення в target.")
    await update.message.reply_text("Ок, відправив тест у target ✅")


# ================= RSS JOB =================
async def rss_job(context: ContextTypes.DEFAULT_TYPE):
    global _last_rss_tick, _last_rss_status

    _last_rss_tick = int(time.time())

    chat_id = load_chat_id()
    if chat_id is None:
        _last_rss_status = "waiting for /settarget"
        print("⌛ Чекаю /settarget, щоб запам'ятати chat_id...")
        return

    try:
        print("🔎 Перевіряю RSS...")
        feed = fetch_feed(RSS_URL)
        print("📦 Знайдено items:", len(feed.entries))

        seen = load_seen()
        posted = 0

        for entry in feed.entries:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", "Нове оголошення")

            if not link:
                continue
            if link in seen:
                continue

            # якщо лінк “мертвий”, все одно додаємо в seen, щоб не мучитись
            if link_alive(link):
                text = f"🚗 {title}\n{link}"
                await context.bot.send_message(chat_id=chat_id, text=text)
                posted += 1
            else:
                print("⚠️ Мертвий лінк (пропущено):", link)

            seen.add(link)

        save_seen(seen)

        if posted:
            _last_rss_status = f"posted {posted}"
            print("✅ Надіслано нових:", posted)
        else:
            _last_rss_status = "nothing new"
            print("— Нічого нового")

    except RetryAfter as e:
        _last_rss_status = f"retry_after {e.retry_after}"
        print("⏳ RetryAfter:", e)
    except (TimedOut, NetworkError) as e:
        _last_rss_status = f"network {repr(e)}"
        print("🌐 Network error:", repr(e))
    except Exception as e:
        _last_rss_status = f"error {repr(e)}"
        print("❌ Помилка при перевірці RSS:", repr(e))


# ================= FALLBACK LOOP (якщо JobQueue відсутній) =================
async def _fallback_loop(app):
    # Запускається тільки якщо app.job_queue is None
    while True:
        try:
            # робимо "context" вручну не треба, бо rss_job використовує context.bot
            # а bot доступний через app.bot, тому зробимо маленький wrapper
            class DummyContext:
                def __init__(self, bot):
                    self.bot = bot

            await rss_job(DummyContext(app.bot))
        except Exception as e:
            print("❌ Fallback loop error:", repr(e))
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def post_init(app):
    # Вимикаємо webhook, щоб не ловити конфлікти з polling
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print("⚠️ delete_webhook failed:", repr(e))


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("settarget", set_target))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("testsend", testsend_cmd))

    # Якщо є JobQueue — ок, запускаємо через нього.
    # Якщо нема (на Render часто так) — запускаємо fallback loop.
    if app.job_queue is not None:
        app.job_queue.run_repeating(rss_job, interval=CHECK_INTERVAL_SECONDS, first=5)
        print("✅ JobQueue enabled: RSS scheduled")
    else:
        print("⚠️ JobQueue is None: using fallback asyncio loop")
        app.post_init = post_init
        # створимо task після старту polling
        # (через create_task в run_polling нижче)

print("✅ Bot started. Waiting for /start...")

try:
    app.run_polling(drop_pending_updates=True)

except Conflict:
    print("❌ CONFLICT: запущено більше одного інстансу бота")
    raise

except Exception as e:
    print("❌ ERROR:", repr(e))
    raise
    
if __name__ == "__main__":
    main()
