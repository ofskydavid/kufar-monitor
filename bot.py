import requests
import json
import time
import os
from datetime import datetime
from flask import Flask

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = "8620473509:AAFa8BIAUuH5IU8GDrFGz4pn5EGbzvcFZ90"
TELEGRAM_USER_ID = "478140816"
KUFAR_URL = "https://www.kufar.by/l/mobilnye-telefony?oph=1&pos=v.or%3A1%2C5&prc=r%3A0%2C300000&sort=lst.d"
CHECK_INTERVAL = 3          # минуты
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://kufar-monitor.onrender.com")
# =============================================

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")

app = Flask(__name__)

@app.route("/")
def home():
    return "Kufar Monitor Bot is running"

@app.route("/reset")
def reset():
    """Сброс памяти – удаляет seen.json"""
    try:
        if os.path.exists(SEEN_FILE):
            os.remove(SEEN_FILE)
            return "Память очищена. При следующей проверке все текущие объявления придут как новые."
        return "Файл seen.json не найден – и так пусто."
    except Exception as e:
        return f"Ошибка при очистке: {e}"

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
    print(f"[{datetime.now()}] 🔄 Запрашиваю объявления...")
    try:
        resp = requests.get(base, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        ads = data.get("ads", [])
        print(f"[{datetime.now()}] Получено {len(ads)} объявлений от API")
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
        print(f"[{datetime.now()}] ❌ ОШИБКА получения: {e}")
        return None

def send_telegram(ad):
    price_str = ad.get("price", "N/A")
    title = ad.get("title", "Без названия")
    message = f"🆕 {title}\n💵 {price_str}\n🔗 {ad['link']}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": message, "disable_web_page_preview": False}
    print(f"[{datetime.now()}] 📤 Отправляю: {title} | {price_str}")
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"[{datetime.now()}] ❌ ОШИБКА Telegram: {r.status_code} {r.text}")
        else:
            print(f"[{datetime.now()}] ✅ Успешно отправлено")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Исключение при отправке: {e}")

def main_loop():
    seen = load_seen()
    ads = fetch_ads()
    if ads is None:
        return
    if not seen:
        # Первый запуск – молча сохраняем всё как просмотренное, НЕ отправляем
        seen = [ad["id"] for ad in ads]
        save_seen(seen)
        print(f"[{datetime.now()}] 🔇 Первичная загрузка: {len(seen)} ID сохранено (уведомления не отправлялись).")
        print("   Чтобы получить текущие объявления сейчас, открой /reset в браузере.")
    else:
        new_ads = [ad for ad in ads if ad["id"] not in seen]
        if new_ads:
            print(f"[{datetime.now()}] 🔔 НОВЫХ: {len(new_ads)}")
            for ad in new_ads:
                send_telegram(ad)
                seen.append(ad["id"])
            save_seen(seen)
        else:
            print(f"[{datetime.now()}] Новых нет (отслеживается {len(seen)} ID)")

def schedule_check():
    while True:
        try:
            requests.get(SELF_URL, timeout=5)
        except:
            pass
        main_loop()
        time.sleep(CHECK_INTERVAL * 60)

if __name__ == "__main__":
    import threading
    monitor_thread = threading.Thread(target=schedule_check)
    monitor_thread.daemon = True
    monitor_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
