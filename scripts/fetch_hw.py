import json
import os
from datetime import datetime, timedelta, timezone
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])

# Сколько дней хранить задания в JSON
KEEP_DAYS = 365

TEACHERS = {
    593528222: "Вайбкоддинг",
    111111111: "Математика",
    222222222: "Українська мова",
    333333333: "Німецька мова",
}

DATA_FILE = "data/homework.json"
DATE_FORMAT = "%Y-%m-%d %H:%M"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"last_update_id": 0, "items": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prune_old_items(items, keep_days=KEEP_DAYS):
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    fresh_items = []

    for item in items:
        date_str = item.get("date_utc")
        if not date_str:
            fresh_items.append(item)
            continue
        try:
            item_dt = datetime.strptime(date_str, DATE_FORMAT).replace(tzinfo=timezone.utc)
            if item_dt >= cutoff:
                fresh_items.append(item)
        except ValueError:
            # Если формат даты в старой записи отличается — сохраняем, чтобы не потерять
            fresh_items.append(item)

    return fresh_items


def main():
    data = load_data()
    offset = data.get("last_update_id", 0) + 1

    resp = requests.get(API_URL, params={"offset": offset, "timeout": 10}, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")

    updates = payload.get("result", [])
    max_update_id = data.get("last_update_id", 0)
    new_items = []

    for upd in updates:
        max_update_id = max(max_update_id, upd["update_id"])
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        if msg.get("chat", {}).get("id") != TARGET_CHAT_ID:
            continue

        sender = msg.get("from", {})
        sender_id = sender.get("id")
        text = msg.get("text") or msg.get("caption")

        if not text:
            continue

        if sender_id in TEACHERS:
            dt = datetime.fromtimestamp(msg["date"], tz=timezone.utc).strftime(DATE_FORMAT)
            new_items.append({
                "message_id": msg["message_id"],
                "subject": TEACHERS[sender_id],
                "teacher": sender.get("first_name", ""),
                "text": text.strip(),
                "date_utc": dt,
            })

    data["last_update_id"] = max_update_id

    # Объединяем старые и новые записи, затем удаляем всё старше KEEP_DAYS
    combined = new_items + data.get("items", [])
    data["items"] = prune_old_items(combined, KEEP_DAYS)

    save_data(data)
    print(f"Новых добавлено: {len(new_items)}. Всего актуальных записей: {len(data['items'])}.")


if __name__ == "__main__":
    main()
