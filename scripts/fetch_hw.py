import json
import os
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
# ID группы (обычно отрицательное число, например -1001234567890)
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])

# Словарь соответствия: Telegram user_id учителя -> Предмет
TEACHERS = {
    593528222: "Вайбкоддинг",
    111111111: "Математика",
    222222222: "Українська мова",
    333333333: "Німецька мова",
}

DATA_FILE = "data/homework.json"
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


def main():
    data = load_data()
    offset = data.get("last_update_id", 0) + 1

    resp = requests.get(API_URL, params={"offset": offset, "timeout": 10}, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")

    updates = payload.get("result", [])
    if not updates:
        print("Новых обновлений нет.")
        return

    new_items = []
    max_update_id = data.get("last_update_id", 0)

    for upd in updates:
        max_update_id = max(max_update_id, upd["update_id"])
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue

        # Проверяем, что сообщение из нужной группы
        if msg.get("chat", {}).get("id") != TARGET_CHAT_ID:
            continue

        sender = msg.get("from", {})
        sender_id = sender.get("id")
        text = msg.get("text") or msg.get("caption")

        if not text:
            continue

        # Фильтр по списку учителей
        if sender_id in TEACHERS:
            dt = datetime.fromtimestamp(msg["date"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            new_items.append({
                "message_id": msg["message_id"],
                "subject": TEACHERS[sender_id],
                "teacher": sender.get("first_name", ""),
                "text": text.strip(),
                "date_utc": dt,
            })

    data["last_update_id"] = max_update_id
    if new_items:
        # Добавляем новые задания в начало и храним последние 100 записей
        data["items"] = (new_items + data["items"])[:100]
        print(f"Добавлено заданий: {len(new_items)}")
    else:
        print("Новых заданий от учителей не найдено.")

    save_data(data)


if __name__ == "__main__":
    main()
