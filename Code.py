import json
import os
import time
import datetime
import calendar
import urllib.request
import urllib.parse
import traceback

BOT_TOKEN = "8863515134:AAHxqgxpJCMGjShDeCKLCUc83LdOpDvkKYM"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

MONTHS = [
    "", "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"
]
WEEKDAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

CATEGORIES = ["💼 Робота", "🎓 Навчання", "🏠 Дім", "🛍 Покупки", "🎨 Хобі", "Інша..."]
PRIORITIES = ["Низький", "Середній", "Високий"]

REMINDER_INTERVAL_SECONDS = 3600

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_json(filename):
    ensure_data_dir()
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_json(filename, data):
    ensure_data_dir()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def api_call(method, params):
    url = BASE_URL + method
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("api_call error:", e)
        return None

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "text": text}
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api_call("sendMessage", params)

def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api_call("editMessageText", params)

def answer_callback(callback_id, text=None, show_alert=False):
    params = {"callback_query_id": callback_id}
    if text:
        params["text"] = text
        params["show_alert"] = "true" if show_alert else "false"
    return api_call("answerCallbackQuery", params)

def main_keyboard_markup():
    keyboard = [["➕ Додати завдання", "📋 Мої завдання"], ["🔄 Почати спочатку"]]
    return {"keyboard": keyboard, "resize_keyboard": True}

def inline_categories():
    kb = []
    row = []
    for i, c in enumerate(CATEGORIES, 1):
        row.append({"text": c, "callback_data": f"cat:{i}"})
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([{"text": "Скасувати", "callback_data": "cancel"}])
    return {"inline_keyboard": kb}

def inline_priorities():
    kb = []
    row = []
    for i, p in enumerate(PRIORITIES, 1):
        row.append({"text": p, "callback_data": f"prio:{i}"})
    kb.append(row)
    kb.append([{"text": "Скасувати", "callback_data": "cancel"}])
    return {"inline_keyboard": kb}

def build_inline_calendar(year, month):
    cal = calendar.monthcalendar(year, month)
    kb = []
    # header: month year (non-clickable)
    kb.append([{"text": f"{MONTHS[month]} {year}", "callback_data": "ignore"}])
    # weekdays row
    weekday_row = [{"text": wd, "callback_data": "ignore"} for wd in WEEKDAYS_UA]
    kb.append(weekday_row)
    # day rows
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append({"text": " ", "callback_data": "ignore"})
            else:
                row.append({"text": str(day), "callback_data": f"cal:day:{year}:{month}:{day}"})
        kb.append(row)
    # prev/next row
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    kb.append([
        {"text": f"« {MONTHS[prev_month]} {prev_year}", "callback_data": f"cal:prev:{prev_year}:{prev_month}"},
        {"text": f"{MONTHS[next_month]} {next_year} »", "callback_data": f"cal:next:{next_year}:{next_month}"}
    ])
    kb.append([{"text": "Скасувати", "callback_data": "cancel"}])
    return {"inline_keyboard": kb}


def task_action_keyboard(task_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✏️ Редагувати", "callback_data": f"task:edit:{task_id}"},
                {"text": "✅ Виконано", "callback_data": f"task:done:{task_id}"},
                {"text": "🗑 Видалити", "callback_data": f"task:delete:{task_id}"}
            ]
        ]
    }

def make_task_id():
    return str(int(time.time() * 1000))

def format_task_text(task):
    name = task.get("name", "")
    date = task.get("date", "")
    category = task.get("category", "-")
    priority = task.get("priority", "-")
    desc = task.get("description", "")
    status = task.get("status", "заплановане")
    date_display = date
    return (f"📌 <b>{name}</b>\n"
            f"🗓 {date_display}\n"
            f"📂 {category}    🔔 {priority}    ✅ {status}\n"
            f"📝 {desc if desc else '-'}")

def start_or_reset_user(chat_id, users):
    users[str(chat_id)] = {
        "state": "enter_name",
        "temp_task": {},
        "name": None,
        "editing_task": None,
    }
    save_json(USERS_FILE, users)
    greeting = (
        "Привіт!\n\n"
        "💫Я — твій цифровий помічник Планувальник завдань.\n"
        "Разом ми впораємося з будь-яким списком справ — від навчання до відпочинку!\n"
        "Почнемо день продуктивно?"
    )
    send_message(chat_id, greeting)
    send_message(chat_id, "👋 Введи своє ім’я (або нікнейм):", reply_markup=main_keyboard_markup())

def list_user_tasks_messages(chat_id, tasks):
    user_tasks = [t for t in tasks.values() if str(t.get("user_id")) == str(chat_id)]
    if not user_tasks:
        send_message(chat_id, "📭 У тебе ще немає завдань.", reply_markup=main_keyboard_markup())
        return

    try:
        user_tasks.sort(key=lambda x: (x.get("date", ""), x.get("id")))
    except Exception:
        pass
    for t in user_tasks:
        text = format_task_text(t)
        send_message(chat_id, text, reply_markup=task_action_keyboard(t["id"]))

def create_task_from_temp(chat_id, users, tasks):
    user = users.get(str(chat_id))
    temp = user.get("temp_task", {})
    if not temp.get("name") or not temp.get("date"):
        send_message(chat_id, "⚠️ Неможливо створити завдання: не вистачає даних.", reply_markup=main_keyboard_markup())
        user["state"] = "main_menu"
        user["temp_task"] = {}
        save_json(USERS_FILE, users)
        return
    task_id = make_task_id()
    tasks[task_id] = {
        "id": task_id,
        "user_id": chat_id,
        "name": temp.get("name"),
        "category": temp.get("category", "-"),
        "description": temp.get("description", ""),
        "priority": temp.get("priority", "-"),
        "date": temp.get("date"),
        "status": "заплановане",
        "reminder_sent": False
    }
    save_json(TASKS_FILE, tasks)
    send_message(chat_id, f"✅ Завдання «{temp.get('name')}» створено на {temp.get('date')}.", reply_markup=main_keyboard_markup())
    user["state"] = "main_menu"
    user["temp_task"] = {}
    save_json(USERS_FILE, users)
    send_message(chat_id, format_task_text(tasks[task_id]), reply_markup=task_action_keyboard(task_id))

def handle_callback(update):
    cq = update["callback_query"]
    data = cq.get("data")
    from_user = cq["from"]
    chat_id = cq["message"]["chat"]["id"] if "message" in cq and "chat" in cq["message"] else from_user["id"]
    callback_id = cq.get("id")
    message = cq.get("message")
    message_id = message.get("message_id") if message else None

    users = load_json(USERS_FILE)
    tasks = load_json(TASKS_FILE)
    user = users.get(str(chat_id), {"state": "main_menu", "temp_task": {}, "editing_task": None})

    try:
        if not data:
            answer_callback(callback_id)
            return

        # Cancel universal
        if data == "cancel":
            user["state"] = "main_menu"
            user["temp_task"] = {}
            user["editing_task"] = None
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            answer_callback(callback_id)
            send_message(chat_id, "❌ Дію скасовано.", reply_markup=main_keyboard_markup())
            return

        if data.startswith("cat:"):
            _, idx = data.split(":")
            idx = int(idx)
            if idx <= len(CATEGORIES):
                chosen = CATEGORIES[idx - 1]
                if chosen == "Інша...":
                    user["state"] = "custom_category"
                    users[str(chat_id)] = user
                    save_json(USERS_FILE, users)
                    answer_callback(callback_id)
                    send_message(chat_id, "Введи свою категорію (або 'Скасувати'):", reply_markup=main_keyboard_markup())
                    return
                else:
                    user["temp_task"]["category"] = chosen
                    user["state"] = "enter_description"
                    users[str(chat_id)] = user
                    save_json(USERS_FILE, users)
                    answer_callback(callback_id)
                    send_message(chat_id, "📝 Введи опис завдання (або напиши 'Пропустити'):", reply_markup=main_keyboard_markup())
                    return

        if data.startswith("prio:"):
            _, idx = data.split(":")
            idx = int(idx)
            if 1 <= idx <= len(PRIORITIES):
                pr = PRIORITIES[idx - 1]
                if user.get("state") == "editing_priority" and user.get("editing_task"):
                    tid = user["editing_task"]
                    tasks = load_json(TASKS_FILE)
                    if tid in tasks:
                        tasks[tid]["priority"] = pr
                        save_json(TASKS_FILE, tasks)
                        send_message(chat_id, "✅ Пріоритет змінено.", reply_markup=main_keyboard_markup())
                        user["state"] = "main_menu"
                        user["editing_task"] = None
                        users[str(chat_id)] = user
                        save_json(USERS_FILE, users)
                        answer_callback(callback_id)
                        return
                # else treat as creating flow
                user["temp_task"]["priority"] = pr
                user["state"] = "select_date"
                now = datetime.datetime.now()
                user["temp_task"]["temp_year"] = now.year
                user["temp_task"]["temp_month"] = now.month
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                send_message(chat_id, "📅 Обери дату:", reply_markup=build_inline_calendar(now.year, now.month))
                return

        if data.startswith("cal:"):
            parts = data.split(":")
            action = parts[1]
            if action in ("prev", "next"):
                year = int(parts[2]); month = int(parts[3])
                if action == "prev":
                    m = month - 1
                    y = year
                    if m < 1:
                        m = 12; y -= 1
                else:
                    m = month + 1
                    y = year
                    if m > 12:
                        m = 1; y += 1
                answer_callback(callback_id)
                if message_id:
                    edit_message_text(chat_id, message_id, "📅 Обери дату:", reply_markup=build_inline_calendar(y, m))
                else:
                    send_message(chat_id, "📅 Обери дату:", reply_markup=build_inline_calendar(y, m))
                return
            if action == "day":
                year = int(parts[2]); month = int(parts[3]); day = int(parts[4])
                try:
                    selected = datetime.date(year, month, day)
                except Exception:
                    answer_callback(callback_id, "Невірна дата", show_alert=True)
                    return
                if selected < datetime.date.today():
                    answer_callback(callback_id, "Не можна обрати дату в минулому.", show_alert=True)
                    return
                if user.get("state") == "select_date":
                    user["temp_task"]["date"] = selected.isoformat()
                    users[str(chat_id)] = user
                    save_json(USERS_FILE, users)
                    answer_callback(callback_id)
                    # create task now
                    create_task_from_temp(chat_id, users, tasks)
                    return
                if user.get("state") == "editing_date" and user.get("editing_task"):
                    tid = user["editing_task"]
                    if tid in tasks:
                        tasks[tid]["date"] = selected.isoformat()
                        save_json(TASKS_FILE, tasks)
                        answer_callback(callback_id)
                        send_message(chat_id, f"✅ Дату завдання змінено на {selected.isoformat()}.", reply_markup=main_keyboard_markup())
                        user["state"] = "main_menu"
                        user["editing_task"] = None
                        users[str(chat_id)] = user
                        save_json(USERS_FILE, users)
                        return
                    else:
                        answer_callback(callback_id, "Завдання не знайдено.", show_alert=True)
                        return
                answer_callback(callback_id)
                send_message(chat_id, "ℹ️ Нічого не було змінено (контекст невідомий).", reply_markup=main_keyboard_markup())
                return
        if data.startswith("task:"):
            _, action, tid = data.split(":", 2)
            tasks = load_json(TASKS_FILE)
            if tid not in tasks:
                answer_callback(callback_id, "Завдання не знайдено.", show_alert=True)
                return
            if action == "done":
                tasks[tid]["status"] = "виконане"
                save_json(TASKS_FILE, tasks)
                answer_callback(callback_id, "Позначено як виконане.")
                send_message(chat_id, f"✅ Завдання «{tasks[tid]['name']}» позначено як виконане.", reply_markup=main_keyboard_markup())
                return
            if action == "delete":
                name = tasks[tid].get("name", "")
                del tasks[tid]
                save_json(TASKS_FILE, tasks)
                answer_callback(callback_id, "Видалено.")
                send_message(chat_id, f"🗑 Завдання «{name}» видалено.", reply_markup=main_keyboard_markup())
                return
            if action == "edit":
                user["state"] = "editing_choose_field"
                user["editing_task"] = tid
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                kb = {"inline_keyboard": [
                    [{"text": "Назву", "callback_data": "editfield:name"}, {"text": "Категорію", "callback_data": "editfield:category"}],
                    [{"text": "Опис", "callback_data": "editfield:description"}, {"text": "Пріоритет", "callback_data": "editfield:priority"}],
                    [{"text": "Змінити дату", "callback_data": "editfield:date"}],
                    [{"text": "Скасувати", "callback_data": "cancel"}]
                ]}
                send_message(chat_id, "Оберіть поле для редагування:", reply_markup=kb)
                return
        if data.startswith("editfield:"):
            _, field = data.split(":", 1)
            if field == "date":
                user["state"] = "editing_date"
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                now = datetime.datetime.now()
                answer_callback(callback_id)
                send_message(chat_id, "📅 Оберіть нову дату:", reply_markup=build_inline_calendar(now.year, now.month))
                return
            if field == "priority":
                user["state"] = "editing_priority"
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                send_message(chat_id, "Оберіть новий пріоритет:", reply_markup=inline_priorities())
                return
            if field == "category":
                user["state"] = "editing_category"
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                send_message(chat_id, "Оберіть категорію або введіть свою:", reply_markup=inline_categories())
                return
            if field == "name":
                user["state"] = "editing_name"
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                send_message(chat_id, "Введи нову назву завдання (або 'Скасувати'):", reply_markup=main_keyboard_markup())
                return
            if field == "description":
                user["state"] = "editing_description"
                users[str(chat_id)] = user
                save_json(USERS_FILE, users)
                answer_callback(callback_id)
                send_message(chat_id, "Введи новий опис (або 'Пропустити'/'Скасувати'):", reply_markup=main_keyboard_markup())
                return

        answer_callback(callback_id)
    except Exception as e:
        print("handle_callback error:", e)
        traceback.print_exc()
        try:
            answer_callback(callback_id)
        except Exception:
            pass

def process_message(update):
    msg = update.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    users = load_json(USERS_FILE)
    tasks = load_json(TASKS_FILE)
    if str(chat_id) not in users or text in ("🔄 Почати спочатку", "/start"):
        start_or_reset_user(chat_id, users)
        return


    user = users.get(str(chat_id))
    state = user.get("state", "main_menu")

    if state == "enter_name":
        user["name"] = text
        user["state"] = "main_menu"
        user["temp_task"] = {}
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, f"✅ Дякую, {text}! Обери дію:", reply_markup=main_keyboard_markup())
        return

    if text == "➕ Додати завдання" and state == "main_menu":
        user["state"] = "enter_task_name"
        user["temp_task"] = {}
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, "📝 Введи назву завдання:", reply_markup=main_keyboard_markup())
        return

    if text == "📋 Мої завдання" and state == "main_menu":
        list_user_tasks_messages(chat_id, tasks)
        return
    if text == "📊 Статистика" and state == "main_menu":
        show_user_statistics(chat_id, tasks)
        return

    if state == "enter_task_name":
        user["temp_task"] = {"name": text}
        user["state"] = "select_category"
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, f"📂 Оберіть категорію для «{text}»:",
                     reply_markup=inline_categories())
        return

    if state == "custom_category":
        if text == "Скасувати":
            user["state"] = "main_menu"
            user["temp_task"] = {}
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        user["temp_task"]["category"] = text
        user["state"] = "enter_description"
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, "📝 Введи опис завдання (або напиши 'Пропустити'):", reply_markup=main_keyboard_markup())
        return

    if state == "enter_description":
        if text == "Пропустити":
            user["temp_task"]["description"] = ""
        else:
            user["temp_task"]["description"] = text
        user["state"] = "select_priority"
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, "🔔 Обери рівень пріоритету:", reply_markup=inline_priorities())
        return

    if state == "editing_name":
        if text == "Скасувати":
            user["state"] = "main_menu"
            user["editing_task"] = None
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        tid = user.get("editing_task")
        tasks = load_json(TASKS_FILE)
        if tid and tid in tasks:
            tasks[tid]["name"] = text
            save_json(TASKS_FILE, tasks)
            send_message(chat_id, "✅ Назву змінено.", reply_markup=main_keyboard_markup())
        else:
            send_message(chat_id, "⚠️ Не вдалося змінити назву.", reply_markup=main_keyboard_markup())
        user["state"] = "main_menu"
        user["editing_task"] = None
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        return

    if state == "editing_category":
        if text == "Скасувати":
            user["state"] = "main_menu"
            user["editing_task"] = None
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        tid = user.get("editing_task")
        tasks = load_json(TASKS_FILE)
        if tid and tid in tasks:
            tasks[tid]["category"] = text
            save_json(TASKS_FILE, tasks)
            send_message(chat_id, "✅ Категорію змінено.", reply_markup=main_keyboard_markup())
        else:
            send_message(chat_id, "⚠️ Не вдалося змінити категорію.", reply_markup=main_keyboard_markup())
        user["state"] = "main_menu"
        user["editing_task"] = None
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        return

    if state == "editing_description":
        if text in ("Скасувати",):
            user["state"] = "main_menu"
            user["editing_task"] = None
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        tid = user.get("editing_task")
        tasks = load_json(TASKS_FILE)
        if text == "Пропустити":
            send_message(chat_id, "ℹ️ Опис залишено без змін.", reply_markup=main_keyboard_markup())
        else:
            if tid and tid in tasks:
                tasks[tid]["description"] = text
                save_json(TASKS_FILE, tasks)
                send_message(chat_id, "✅ Опис змінено.", reply_markup=main_keyboard_markup())
            else:
                send_message(chat_id, "⚠️ Не вдалося змінити опис.", reply_markup=main_keyboard_markup())
        user["state"] = "main_menu"
        user["editing_task"] = None
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        return

    if state == "editing_priority":
        if text == "Скасувати":
            user["state"] = "main_menu"
            user["editing_task"] = None
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        if text not in PRIORITIES:
            send_message(chat_id, "⚠️ Оберіть пріоритет кнопкою.", reply_markup=inline_priorities())
            return
        tid = user.get("editing_task")
        tasks = load_json(TASKS_FILE)
        if tid and tid in tasks:
            tasks[tid]["priority"] = text
            save_json(TASKS_FILE, tasks)
            send_message(chat_id, "✅ Пріоритет змінено.", reply_markup=main_keyboard_markup())
        else:
            send_message(chat_id, "⚠️ Не вдалося змінити пріоритет.", reply_markup=main_keyboard_markup())
        user["state"] = "main_menu"
        user["editing_task"] = None
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        return
    if state == "custom_category":
        if text == "Скасувати":
            user["state"] = "main_menu"
            user["temp_task"] = {}
            users[str(chat_id)] = user
            save_json(USERS_FILE, users)
            send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
            return
        user["temp_task"]["category"] = text
        user["state"] = "enter_description"
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, "📝 Введи опис завдання (або напиши 'Пропустити'):", reply_markup=main_keyboard_markup())
        return
    if text == "Скасувати":
        user["state"] = "main_menu"
        user["temp_task"] = {}
        user["editing_task"] = None
        users[str(chat_id)] = user
        save_json(USERS_FILE, users)
        send_message(chat_id, "❌ Скасовано.", reply_markup=main_keyboard_markup())
        return

    send_message(chat_id, "🙃 Не зовсім зрозумів. Скористайся меню:", reply_markup=main_keyboard_markup())

def check_and_send_reminders():
    tasks = load_json(TASKS_FILE)
    now = datetime.date.today()
    tomorrow = now + datetime.timedelta(days=1)
    for tid, task in list(tasks.items()):
        if task.get("status") == "заплановане" and not task.get("reminder_sent", False):
            try:
                due_date = datetime.date.fromisoformat(task.get("date"))
            except Exception:
                continue
            if due_date == tomorrow:
                # send reminder to user
                uid = task.get("user_id")
                text = f"🔔 Нагадування: завдання «{task.get('name')}» має дедлайн завтра ({task.get('date')})."
                send_message(uid, text, reply_markup=main_keyboard_markup())
                tasks[tid]["reminder_sent"] = True
    save_json(TASKS_FILE, tasks)

def main():
    ensure_data_dir()
    offset = None
    last_reminder_check = 0
    print("🤖 Бот запущено! Очікування повідомлень...")
    while True:
        try:
            url = BASE_URL + "getUpdates"
            if offset:
                url += f"?offset={offset}"
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    try:
                        handle_callback(update)
                    except Exception as e:
                        print("callback handling error:", e)
                        traceback.print_exc()
                else:
                    try:
                        process_message(update)
                    except Exception as e:
                        print("message handling error:", e)
                        traceback.print_exc()
            now_ts = time.time()
            if now_ts - last_reminder_check >= REMINDER_INTERVAL_SECONDS:
                try:
                    check_and_send_reminders()
                except Exception as e:
                    print("reminder check error:", e)
                last_reminder_check = now_ts
        except Exception as e:
            print("Main loop error:", e)
            traceback.print_exc()
            time.sleep(2)
        time.sleep(0.3)

def main_keyboard_markup():
    keyboard = [
        ["➕ Додати завдання", "📋 Мої завдання", "📊 Статистика"], 
        ["🔄 Почати спочатку"]
    ]
    return {"keyboard": keyboard, "resize_keyboard": True}

def show_user_statistics(chat_id, tasks):
    user_tasks = [t for t in tasks.values() if str(t.get("user_id")) == str(chat_id)]
    
    if not user_tasks:
        send_message(chat_id, "📊 У тебе ще немає жодного завдання для розрахунку статистики. Створи щось! 😉", reply_markup=main_keyboard_markup())
        return

    total = len(user_tasks)
    done = len([t for t in user_tasks if t.get("status") == "виконане"])
    planned = total - done

    success_rate = int((done / total) * 100) if total > 0 else 0

    if success_rate == 100:
        motivation = "🏆 Ідеально! Ти справжній продуктивний ніндзя!"
    elif success_rate >= 70:
        motivation = "🚀 Чудовий результат! Продовжуй у тому ж дусі!"
    elif success_rate >= 40:
        motivation = "📈 Хороший рух, половину або навіть більше вже зроблено!"
    else:
        motivation = "🌱 Початок покладено! Крок за кроком до мети."

    stat_text = (
        "📊 <b>Твоя статистика продуктивності:</b>\n\n"
        f"📝 Всього завдань у базі: <b>{total}</b>\n"
        f"✅ Виконано успішно: <b>{done}</b>\n"
        f"⏳ Очікують виконання: <b>{planned}</b>\n\n"
        f"🎯 Рівень продуктивності: <b>{success_rate}%</b>\n"
        f"<i>{motivation}</i>"
    )
    
    send_message(chat_id, stat_text, reply_markup=main_keyboard_markup())

if __name__ == "__main__":
    main()
