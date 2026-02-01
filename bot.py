{\rtf1\ansi\ansicpg1251\cocoartf2820
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fnil\fcharset0 HelveticaNeue;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\deftab560
\pard\pardeftab560\slleading20\partightenfactor0

\f0\fs26 \cf0 mport time\
import feedparser\
import requests\
import os\
from telegram import Bot\
\
TOKEN = os.getenv("8437214679:AAEVoh8BTfbJx15mZcu7VCpsI4ZSB9Vpe3Y\
")\
CHANNEL_ID = os.getenv("8148281047")\
RSS_URL = os.getenv("RSS_URL", "https://www.olx.ua/uk/rss/q-macbook-air/")\
\
bot = Bot(token=8437214679:AAEVoh8BTfbJx15mZcu7VCpsI4ZSB9Vpe3Y\
\pard\pardeftab560\slleading20\pardirnatural\partightenfactor0
\cf0 \
\
\pard\pardeftab560\slleading20\partightenfactor0
\cf0 SEEN_FILE = "seen_links.txt"\
\
def load_seen():\
    if os.path.exists(SEEN_FILE):\
        with open(SEEN_FILE, "r") as f:\
            return set(line.strip() for line in f)\
    return set()\
\
def save_seen(seen):\
    with open(SEEN_FILE, "w") as f:\
        for link in seen:\
            f.write(link + "\\n")\
\
seen_links = load_seen()\
\
while True:\
    try:\
        feed = feedparser.parse(RSS_URL)\
\
        for entry in feed.entries:\
            link = entry.link\
            title = entry.title\
\
            if link not in seen_links:\
                message = f"\uc0\u55356 \u56725  \u1053 \u1086 \u1074 \u1077  \u1086 \u1075 \u1086 \u1083 \u1086 \u1096 \u1077 \u1085 \u1085 \u1103 :\\n\{title\}\\n\{link\}"\
                bot.send_message(chat_id=CHANNEL_ID, text=message)\
                seen_links.add(link)\
                save_seen(seen_links)\
\
        time.sleep(300)  \
\
    except Exception as e:\
        print("\uc0\u1065 \u1086 \u1089 \u1100  \u1087 \u1110 \u1096 \u1083 \u1086  \u1085 \u1077  \u1090 \u1072 \u1082 :", e)\
        time.sleep(60)\
}