import requests
import json
import time
import os
from datetime import datetime
from flask import Flask

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = "8620473509:AAFa8BIAUuH5IU8GDrFGz4pn5EGbzvcFZ90"
TELEGRAM_USER_ID = "478140816"
KUFAR_URL = "https://www.kufar.by/l/r~vitebsk/mobilnye-telefony/mt~android?oph=1&prc=r%3A0%2C50000&sort=lst.d"
CHECK_INTERVAL = 3          # минуты между проверками
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://kufar-monitor.onrender.com")
# =============================================

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")

app = Flask(__name__)

@app.route("/")
def home():
    return "Kufar Monitor Bot is running"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return []

def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(ids, f)

def fetch_ads():
    base = "https://api.kufar.by/search/search?"
    params = {
        "cat": "17010",
        "cur": "BYR",
        "gtsy": "r~vitebsk",
        "oph": "1",
        "size": "30",
        "sort": "lst.d",
        "prc": "r:0,50000"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(base, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        ads = data.get("ads", [])
        result = []
        for ad in ads:
            ad_id = ad.get("ad_id")
            title = ad.get("subject")
            price = ad.get("price")
            link = ad.get("ad_link")
            if ad_id and link:
                result.append({"id": str(ad_id), "title": title, "price": price, "link": link})
        return result
    except Exception as e:
        print(f"[!] Ошибка получения: {e}")
        return None

def send_telegram(ad):
    price_str = ad.get("price", "N/A")
    title = ad.get("title", "Без названия")
    message = f"🆕 {title}\n💵 {price_str}\n🔗 {ad['link']}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": message, "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def main_loop():
    seen = load_seen()
    ads = fetch_ads()
    if ads is not None:
        if not seen:
            seen = [ad["id"] for ad in ads]
            save_seen(seen)
            print(f"Первичная загрузка: {len(seen)} объявлений")
        else:
            new_ads = [ad for ad in ads if ad["id"] not in seen]
            if new_ads:
                for ad in new_ads:
                    send_telegram(ad)
                    seen.append(ad["id"])
                save_seen(seen)

def schedule_check():
    while True:
        # Пинг самого себя, чтобы Render не уснул
        try:
            requests.get(SELF_URL, timeout=5)
        except:
            pass
        # Проверка объявлений
        main_loop()
        time.sleep(CHECK_INTERVAL * 60)

if __name__ == "__main__":
    import threading
    monitor_thread = threading.Thread(target=schedule_check)
    monitor_thread.daemon = True
    monitor_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
