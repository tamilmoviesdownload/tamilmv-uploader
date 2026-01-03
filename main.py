# --- IMPORTS ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# --- TEMP FIX for Python 3.13 ---
import sys, types
imghdr = types.ModuleType("imghdr")
imghdr.what = lambda *args, **kwargs: None
sys.modules['imghdr'] = imghdr

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
import os
import re
import urllib3
from threading import Thread

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = "-1002754017596"
EARN4LINK_API_KEY = os.environ.get("EARN4LINK_API_KEY", "")
DOWNLOAD_TUTORIAL_LINK = "https://t.me/howtodownloadtlink"

POSTER_FOLDER = "posters"

if not BOT_TOKEN or not EARN4LINK_API_KEY:
    raise ValueError("BOT_TOKEN and EARN4LINK_API_KEY must be set")

bot = telegram.Bot(token=BOT_TOKEN)

# --- FLASK APP ---
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "✅ TamilMV Bot Running on Render"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run, daemon=True).start()

# --- TITLE CLEANING ---
def clean_title(raw):
    t = raw.lower()

    remove_words = [
        "tamil", "hq", "predvd", "web-dl", "hdrip", "bluray",
        "brrip", "dvdrip", "clean", "audio", "true", "uncut", "esub"
    ]

    for w in remove_words:
        t = re.sub(rf"\b{w}\b", "", t)

    t = re.sub(r"\[.*?\]|\(.*?\)", "", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t.title()

# --- TELEGRAM DEEPLINK ---
def make_telegram_link(title):
    slug = title.lower().replace(" ", "-")
    return f"https://telegram.me/tamilmovierbot?start=getfile-{slug}"

# --- SHORT LINK ---
def shorten_link(url):
    try:
        api = f"https://nowshort.com/api?api={EARN4LINK_API_KEY}&url={url}"
        r = requests.get(api, timeout=10, verify=False).json()
        return r.get("shortenedUrl", url)
    except:
        return url

# --- POSTER DOWNLOAD ---
def download_poster(soup, title):
    os.makedirs(POSTER_FOLDER, exist_ok=True)
    img = soup.find("img", class_="ipsImage")
    if not img:
        return None

    url = img.get("data-src") or img.get("src")
    path = os.path.join(POSTER_FOLDER, title.replace(" ", "_") + ".jpg")

    try:
        with open(path, "wb") as f:
            f.write(requests.get(url, timeout=10, verify=False).content)
        return path
    except:
        return None

# --- CAPTION ---
def make_caption(title):
    return f"""🎬 <b>{title}</b>

📘 <b>Download Tutorial 👇</b>
👉 <a href="{DOWNLOAD_TUTORIAL_LINK}">Click Here</a>"""

# --- MAIN PROCESS ---
def process_and_upload(page_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(page_url, headers=headers, timeout=15, verify=False)
    soup = BeautifulSoup(res.text, "html.parser")

    h1 = soup.find("h1")
    raw_title = h1.get_text(strip=True) if h1 else "Untitled"

    movie_title = clean_title(raw_title)
    poster = download_poster(soup, movie_title)

    # --- TORRENT BUTTONS ---
    torrent_buttons = []
    for a in soup.find_all("a", href=True):
        if "magnet:" in a["href"]:
            size = "Unknown"
            prev = a.find_previous("a")
            if prev:
                m = re.search(r"(\d+(\.\d+)?\s?(GB|MB))", prev.text, re.I)
                if m:
                    size = m.group(1)

            torrent_buttons.append(
                InlineKeyboardButton(size, url=shorten_link(a["href"]))
            )

    if not torrent_buttons:
        return False, "No torrents found"

    # --- BUTTON LAYOUT (AS REQUESTED) ---
    tg_link = make_telegram_link(movie_title)
    buttons = []

    # TOP
    buttons.append([
        InlineKeyboardButton("Torrent Files ⏬", callback_data="torrent_files")
    ])

    # MIDDLE (TORRENT SIZES)
    for i in range(0, len(torrent_buttons), 2):
        buttons.append(torrent_buttons[i:i + 2])

    # BOTTOM
    buttons.append([
        InlineKeyboardButton("Telegram File Download 📥", url=tg_link)
    ])

    markup = InlineKeyboardMarkup(buttons)
    caption = make_caption(movie_title)

    # --- SEND ---
    if poster:
        with open(poster, "rb") as p:
            bot.send_photo(
                chat_id=CHAT_ID,
                photo=InputFile(p),
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML"
            )
    else:
        bot.send_message(
            chat_id=CHAT_ID,
            text=caption,
            reply_markup=markup,
            parse_mode="HTML"
        )

    return True, "Uploaded"

# --- API ROUTE ---
@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    success, msg = process_and_upload(data["url"])
    return jsonify({"message": msg})

# --- START ---
if __name__ == "__main__":
    keep_alive()
    while True:
        pass
