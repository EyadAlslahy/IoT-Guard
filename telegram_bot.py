# =====================================================
#  IoT Guard - Telegram Bot (With Settings Menu)
# =====================================================

import requests
import time
import json
import os

# ============ Settings ============
TOKEN = "8986750534:AAHel6Wvg5AmHN6YykcFRJnChJqEtrO4E6I"
CHAT_ID = "6989201477"

PENDING_FILE = "pending_devices.json"
DECISIONS_FILE = "decisions.json"
# ============================================


def send_message(text, keyboard=None, reply_keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    if reply_keyboard:
        payload["reply_markup"] = reply_keyboard

    r = requests.post(url, json=payload)
    return r.json()


def edit_message_text(message_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    payload = {
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard is not None:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    r = requests.post(url, json=payload)
    return r.json()


def answer_callback(callback_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_id, "text": text})


def load_pending():
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_pending(d):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def load_decisions():
    if os.path.exists(DECISIONS_FILE):
        with open(DECISIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_decisions(d):
    with open(DECISIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# =====================================================
#  الأزرار الدائمة
# =====================================================

def send_settings_menu():
    keyboard = [
        [{"text": "📱 الأجهزة المتصلة", "callback_data": "settings_connected"}],
        [{"text": "✅ القائمة البيضاء", "callback_data": "settings_whitelist"}],
        [{"text": "⛔ القائمة السوداء", "callback_data": "settings_blacklist"}]
    ]
    send_message("⚙️ <b>الإعدادات</b>\n\nاختر:", keyboard)


def send_permanent_keyboard():
    reply_kb = {
        "keyboard": [[{"text": "⚙️ الإعدادات"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }
    send_message("✅ <b>البوت جاهز</b>\nاستخدم زر الإعدادات بالأسفل للتحكم.",
                 reply_keyboard=reply_kb)


# =====================================================
#  معالجة أزرار الإعدادات
# =====================================================

def handle_settings_callback(cb, session, fetch_lists_func,
                             del_white_func, del_black_func,
                             block_func, allow_func,
                             get_devices_func=None,
                             load_names_func=None):
    cb_data = cb["data"]
    message_id = cb["message"]["message_id"]
    cb_id = cb["id"]

    # ===== الأجهزة المتصلة =====
    if cb_data == "settings_connected":
        answer_callback(cb_id, "📱")
        devices = get_devices_func(session) if get_devices_func else []

        if not devices:
            text = "📱 <b>لا توجد أجهزة متصلة</b>"
        else:
            text = f"📱 <b>الأجهزة المتصلة ({len(devices)})</b>\n\n"
            for i, d in enumerate(devices, 1):
                text += f"{i}. <b>{d['name']}</b>\n"
                text += f"   MAC: <code>{d['mac']}</code>\n"
                text += f"   IP: <code>{d['ip']}</code>\n\n"

        keyboard = [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]]
        edit_message_text(message_id, text, keyboard)

    # ===== القائمة البيضاء =====
    elif cb_data == "settings_whitelist":
        answer_callback(cb_id, "✅")
        bl, wl = fetch_lists_func(session)
        names = load_names_func() if load_names_func else {}

        if not wl:
            text = "✅ <b>القائمة البيضاء فارغة</b>"
            keyboard = [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]]
        else:
            text = f"✅ <b>القائمة البيضاء ({len(wl)})</b>\n\n"
            keyboard = []
            for mac in wl:
                dev_name = names.get(mac, "Unknown")
                text += f"📱 <b>{dev_name}</b>\n"
                text += f"<code>{mac}</code>\n\n"
                keyboard.append([
                    {"text": f"⛔ حظر {mac[-5:]}", "callback_data": f"wl_block:{mac}"},
                    {"text": f"🗑️ حذف {mac[-5:]}", "callback_data": f"wl_del:{mac}"}
                ])
            keyboard.append([{"text": "🔙 رجوع", "callback_data": "settings_back"}])

        edit_message_text(message_id, text, keyboard)

    # ===== القائمة السوداء =====
    elif cb_data == "settings_blacklist":
        answer_callback(cb_id, "⛔")
        bl, wl = fetch_lists_func(session)
        names = load_names_func() if load_names_func else {}

        if not bl:
            text = "⛔ <b>القائمة السوداء فارغة</b>"
            keyboard = [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]]
        else:
            text = f"⛔ <b>القائمة السوداء ({len(bl)})</b>\n\n"
            keyboard = []
            for mac in bl:
                dev_name = names.get(mac, "Unknown")
                text += f"📱 <b>{dev_name}</b>\n"
                text += f"<code>{mac}</code>\n\n"
                keyboard.append([
                    {"text": f"✅ سماح {mac[-5:]}", "callback_data": f"bl_allow:{mac}"},
                    {"text": f"🗑️ حذف {mac[-5:]}", "callback_data": f"bl_del:{mac}"}
                ])
            keyboard.append([{"text": "🔙 رجوع", "callback_data": "settings_back"}])

        edit_message_text(message_id, text, keyboard)

    # ===== رجوع =====
    elif cb_data == "settings_back":
        answer_callback(cb_id, "رجوع")
        keyboard = [
            [{"text": "📱 الأجهزة المتصلة", "callback_data": "settings_connected"}],
            [{"text": "✅ القائمة البيضاء", "callback_data": "settings_whitelist"}],
            [{"text": "⛔ القائمة السوداء", "callback_data": "settings_blacklist"}]
        ]
        edit_message_text(message_id, "⚙️ <b>الإعدادات</b>\n\nاختر:", keyboard)

    # ===== حظر من البيضاء =====
    elif cb_data.startswith("wl_block:"):
        mac = cb_data.split(":", 1)[1]
        block_func(session, mac)
        answer_callback(cb_id, f"⛔ تم الحظر")
        edit_message_text(message_id,
                          f"⛔ <b>تم حظر الجهاز</b>\n<code>{mac}</code>\n\n"
                          f"نُقل من البيضاء إلى السوداء.",
                          [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]])

    # ===== حذف من البيضاء =====
    elif cb_data.startswith("wl_del:"):
        mac = cb_data.split(":", 1)[1]
        del_white_func(session, mac)
        answer_callback(cb_id, f"🗑️ تم الحذف")
        edit_message_text(message_id,
                          f"🗑️ <b>تم حذف الجهاز من البيضاء</b>\n<code>{mac}</code>\n\n"
                          f"سيُكتشف كجهاز جديد.",
                          [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]])

    # ===== سماح من السوداء =====
    elif cb_data.startswith("bl_allow:"):
        mac = cb_data.split(":", 1)[1]
        allow_func(session, mac)
        answer_callback(cb_id, f"✅ تم السماح")
        edit_message_text(message_id,
                          f"✅ <b>تم السماح للجهاز</b>\n<code>{mac}</code>\n\n"
                          f"نُقل من السوداء إلى البيضاء.",
                          [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]])

    # ===== حذف من السوداء =====
    elif cb_data.startswith("bl_del:"):
        mac = cb_data.split(":", 1)[1]
        del_black_func(session, mac)
        answer_callback(cb_id, f"🗑️ تم الحذف")
        edit_message_text(message_id,
                          f"🗑️ <b>تم حذف الجهاز من السوداء</b>\n<code>{mac}</code>\n\n"
                          f"سيُكتشف كجهاز جديد.",
                          [[{"text": "🔙 رجوع", "callback_data": "settings_back"}]])


# =====================================================
#  تنبيه جهاز جديد
# =====================================================

def send_device_alert(device):
    mac = device["mac"]
    name = device["name"]
    ip = device["ip"]

    text = (
        f"<b>جهاز جديد تم اكتشافه</b>\n\n"
        f"<b>الاسم:</b> {name}\n"
        f"<b>MAC:</b> <code>{mac}</code>\n"
        f"<b>IP:</b> <code>{ip}</code>\n\n"
        f"ما هو الإجراء؟"
    )
    keyboard = [[
        {"text": "✅ قبول", "callback_data": f"accept:{mac}"},
        {"text": "⛔ حظر", "callback_data": f"block:{mac}"}
    ]]
    result = send_message(text, keyboard)
    if result.get("ok"):
        return result["result"]["message_id"]
    return None


def edit_decision_message(message_id, text):
    return edit_message_text(message_id, text, [])


# =====================================================
#  معالجة قرار قبول/حظر
# =====================================================

def process_decision(callback_data, message_id, callback_id):
    parts = callback_data.split(":", 1)
    action = parts[0]
    mac = parts[1]

    decisions = load_decisions()

    if action == "accept":
        decisions[mac] = "accept"
        answer_callback(callback_id, "✅ تم القبول")
        edit_message_text(message_id,
                          f"✅ <b>تم قبول الجهاز</b>\n<code>{mac}</code>", [])
    elif action == "block":
        decisions[mac] = "block"
        answer_callback(callback_id, "⛔ تم الحظر")
        edit_message_text(message_id,
                          f"⛔ <b>تم حظر الجهاز</b>\n<code>{mac}</code>", [])

    save_decisions(decisions)