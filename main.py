# --- IMPORTS ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# --- TEMP FIX for Python 3.13 (imghdr removed) ---
import sys, types
imghdr = types.ModuleType("imghdr")
imghdr.what = lambda *args, **kwargs: None
sys.modules['imghdr'] = imghdr
# -------------------------------------------------

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
import os
import re
import urllib3
from threading import Thread

# --- DISABLE SSL WARNINGS ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CHAT_ID = '-1002754017596'
EARN4LINK_API_KEY = os.environ.get('EARN4LINK_API_KEY', '')

# 🔗 Added Variables (edit anytime)
CHANNEL_LINK = "https://t.me/+s4wwf5daeWRmOGJl"    # Title tap → goes to channel
DOWNLOAD_TUTORIAL_LINK = "https://t.me/howtodownloadtlink"  # Tutorial link

POSTED_FILE = "posted_movies.txt"
POSTER_FOLDER = "posters"

if not BOT_TOKEN or not EARN4LINK_API_KEY:
    raise ValueError("BOT_TOKEN and EARN4LINK_API_KEY must be set in environment variables")

bot = telegram.Bot(token=BOT_TOKEN)

# --- FLASK APP ---
app = Flask(__name__)
CORS(app)

# --- ROOT ROUTE (for uptime tracking) ---
@app.route('/')
def home():
    return "✅ TamilMV Uploader Bot is alive and running on Render!"

# --- KEEP ALIVE THREAD ---
def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- HELPERS ---
def clean_title(raw_title: str) -> str:
    title = raw_title
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(\d{4}\)', '', title)
    title = re.sub(r'WEB[- ]?DL.*|BluRay.*|x264.*|HEVC.*|HDRip.*', '', title, flags=re.I)
    title = title.replace("TRUE", "")
    title = re.sub(r'-{2,}', '-', title)
    return " ".join(title.split()).strip()

def shorten_link(long_url):
    try:
        url = f"https://nowshort.com/api?api={EARN4LINK_API_KEY}&url={long_url}"
        response = requests.get(url, timeout=10, verify=False).json()
        if response.get("status") == "success":
            return response["shortenedUrl"]
        return long_url
    except:
        return long_url

def download_poster(soup, title):
    os.makedirs(POSTER_FOLDER, exist_ok=True)
    image_element = soup.find('img', class_='ipsImage')
    if not image_element:
        return None, None
    image_url = image_element.get('data-src') or image_element.get('src')
    if not image_url:
        return None, None
    ext = os.path.splitext(image_url)[-1]
    if not ext or len(ext) > 5:
        ext = ".jpg"
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    poster_path = os.path.join(POSTER_FOLDER, safe_title + ext)
    try:
        img_data = requests.get(image_url, timeout=10, verify=False).content
        with open(poster_path, "wb") as f:
            f.write(img_data)
        return poster_path, image_url
    except:
        return None, image_url

# 🔗 Title now has hyperlink (goes to your channel)
def make_caption(title):
    return f"""🎬 <b><a href="{CHANNEL_LINK}">{title}</a></b>

📘 <b>Download Tutorial 👇</b>
👉 <a href="{DOWNLOAD_TUTORIAL_LINK}">Click Here</a>"""

# --- UPLOAD FUNCTION ---
def process_and_upload(page_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(page_url, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Title
        title_element = soup.find('h1', class_='ipsType_pageTitle ipsContained_container')
        raw_title = title_element.get_text(strip=True) if title_element else "Untitled"
        movie_title = clean_title(raw_title)

        print(f"🎬 Processing: {movie_title}")

        # Poster
        poster_path, poster_url = download_poster(soup, movie_title)

        # Torrent Links
        torrent_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'magnet:' in href:
                prev = a_tag.find_previous("a", href=True)
                size_text = "Unknown Size"
                if prev and prev.text:
                    size_match = re.search(r'(\d+(\.\d+)?\s?(GB|MB))', prev.text, re.I)
                    if size_match:
                        size_text = size_match.group(1)
                short_link = shorten_link(href)
                torrent_links.append((size_text, short_link))

        if not torrent_links:
            print(f"⚠️ No magnet links found for {movie_title}. Skipping.")
            return False, "⚠️ No magnet links found."

        # Telegram inline buttons
        buttons = [InlineKeyboardButton(size, url=link) for size, link in torrent_links]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        reply_markup = InlineKeyboardMarkup(rows)

        caption = make_caption(movie_title)

        # Upload to Telegram
        if poster_path:
            with open(poster_path, "rb") as photo:
                bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=InputFile(photo),
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
        else:
            bot.send_message(
                chat_id=CHAT_ID,
                text=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

        print(f"✅ Uploaded: {movie_title}")
        return True, f"✅ Uploaded: {movie_title}"

    except Exception as e:
        print(f"❌ Error processing {page_url}: {e}")
        return False, f"❌ Error: {e}"

# --- FLASK ROUTE ---
@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"message": "❌ No URL received"}), 400

    page_url = data["url"].strip()
    success, msg = process_and_upload(page_url)
    return jsonify({"message": msg})

# --- MAIN ENTRY ---
if __name__ == "__main__":
    print("🚀 TamilMV Uploader Bot is running...")
    keep_alive()
    while True:
        pass
