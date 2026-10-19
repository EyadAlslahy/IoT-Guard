# =====================================================
#  IoT Guard - Main Script (Updated)
# =====================================================

import requests
import hashlib
import random
import string
import json
import os
import sys
import time

# ============ SMS ============
sys.path.insert(0, r"E:\IoT")
from sms_sender import send_sms

# ============ Telegram ============
from telegram_bot import (
    send_device_alert,
    process_decision,
    edit_decision_message,
    send_settings_menu,
    send_permanent_keyboard,
    handle_settings_callback
)
import telegram_bot

# ============ PRESENT ============
PRESENT_PATH = r"E:\project\1\present_cipher"
sys.path.insert(0, PRESENT_PATH)
from src.modes import ctr_encrypt

SHARED_KEY = 0x0123456789ABCDEF0123
NONCE = 0xDEADBEEF

# ============ Settings ============
ROUTER_HOST = "mobile.router"
USERNAME = "admin"
PASSWORD = "770101712"
ESP32_IP = "192.168.8.181"
ADMIN_PHONE = "776723322"
PENDING_FILE = "pending_devices.json"
DECISIONS_FILE = "decisions.json"
BLACKLIST_FILE = "router_blacklist.json"
WHITELIST_FILE = "router_whitelist.json"
NAMES_FILE = "mac_names.json"
CHECK_INTERVAL = 30
LOOP_INTERVAL = 2
# ==================================

BASE = f"http://{ROUTER_HOST}/api.cgi"
LAST_UPDATE_ID = None


# =====================================================
#  Helpers
# =====================================================

def generate_user_id():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))


# =====================================================
#  Router - Login
# =====================================================

def get_rand(session, user_id):
    url = f"{BASE}?path=account&method=get_rand&timeout=20"
    r = session.post(url, json={"type": "admin", "user_id": user_id})
    return r.json().get("rand")


def login(session, user_id, rand):
    pwd_hash = hashlib.md5((rand + PASSWORD.lower()).encode()).hexdigest()
    url = f"{BASE}?path=account&method=login&timeout=20"
    payload = {
        "type": "admin",
        "username": USERNAME,
        "password": pwd_hash,
        "user_id": user_id
    }
    r = session.post(url, json=payload)
    return r.json()


def login_session():
    user_id = generate_user_id()
    session = requests.Session()
    rand = get_rand(session, user_id)
    if not rand:
        return None
    result = login(session, user_id, rand)
    if "error" in str(result).lower():
        return None
    return session


# =====================================================
#  Router - Devices
# =====================================================

def get_connected_devices(session):
    url = f"{BASE}?path=statistics&method=get_conn_clients_info&timeout=20"
    r = session.post(url, json={})
    data = r.json()
    devices = []
    try:
        for c in data.get("clients_info", []):
            devices.append({
                "mac":  c.get("mac", "").upper().replace("-", ":"),
                "ip":   c.get("ip", ""),
                "name": c.get("name", "Unknown"),
                "type": c.get("type", "")
            })
    except Exception:
        pass
    return devices


# =====================================================
#  Router - Filter Lists
# =====================================================

def fetch_router_lists(session):
    url = f"{BASE}?path=wireless&method=wifi_get_mac_filter&timeout=20"
    r = session.post(url, json={"wifi_device": "0"})
    data = r.json()
    try:
        ap = data["wireless"].get("AP0", data["wireless"])
        bl = [m.strip().upper() for m in ap.get("maclist_deny", "").replace(",", " ").split() if m.strip()]
        wl = [m.strip().upper() for m in ap.get("maclist_allow", "").replace(",", " ").split() if m.strip()]
    except (KeyError, TypeError):
        bl, wl = [], []
    return bl, wl


def set_filter_lists(session, blacklist, whitelist):
    url = f"{BASE}?path=wireless&method=wifi_set_mac_filter&timeout=20"
    payload = {
        "wifi_device": "0",
        "macfilter": "deny",
        "maclist_deny": " ".join(sorted(set(blacklist))) + " " if blacklist else "",
        "maclist_allow": " ".join(sorted(set(whitelist))) + " " if whitelist else ""
    }
    r = session.post(url, json=payload)
    return r.json()


def sync_router_lists(session):
    bl, wl = fetch_router_lists(session)
    new_bl, new_wl = set(bl), set(wl)
    save_json(BLACKLIST_FILE, list(new_bl))
    save_json(WHITELIST_FILE, list(new_wl))
    print(f"    [Sync] Blacklist: {len(new_bl)} | Whitelist: {len(new_wl)}")
    return new_bl, new_wl


def block_mac_on_router(session, mac):
    mac = mac.upper()
    bl, wl = fetch_router_lists(session)
    wl = [m for m in wl if m != mac]
    if mac not in bl: bl.append(mac)
    return set_filter_lists(session, bl, wl)


def accept_mac_on_router(session, mac):
    mac = mac.upper()
    bl, wl = fetch_router_lists(session)
    bl = [m for m in bl if m != mac]
    if mac not in wl: wl.append(mac)
    return set_filter_lists(session, bl, wl)


def delete_from_whitelist(session, mac):
    mac = mac.upper()
    bl, wl = fetch_router_lists(session)
    wl = [m for m in wl if m != mac]
    return set_filter_lists(session, bl, wl)


def delete_from_blacklist(session, mac):
    mac = mac.upper()
    bl, wl = fetch_router_lists(session)
    bl = [m for m in bl if m != mac]
    return set_filter_lists(session, bl, wl)


# =====================================================
#  Files
# =====================================================

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_pending(): return load_json(PENDING_FILE, {})
def save_pending(d): save_json(PENDING_FILE, d)
def load_decisions(): return load_json(DECISIONS_FILE, {})
def save_decisions(d): save_json(DECISIONS_FILE, d)
def load_names(): return load_json(NAMES_FILE, {})
def save_names(d): save_json(NAMES_FILE, d)


def update_names_from_devices(devices):
    """يُحدّث mapping MAC → Name"""
    names = load_names()
    for d in devices:
        if d["mac"] and d["name"] != "Unknown":
            names[d["mac"]] = d["name"]
    save_names(names)
    return names


# =====================================================
#  ESP32 Communication
# =====================================================

def send_to_esp32(devices, whitelist, blacklist):
    lines = ["DEVICES"]
    for d in devices:
        line = f"{d['mac']}|{d['name']}|{d['ip']}"
        enc = ctr_encrypt(line, SHARED_KEY, NONCE)
        lines.append(enc.hex())

    lines.append("WHITELIST")
    for mac in whitelist:
        lines.append(mac)

    lines.append("BLACKLIST")
    for mac in blacklist:
        lines.append(mac)

    body = "\n".join(lines)
    try:
        requests.post(f"http://{ESP32_IP}/data", data=body,
                      headers={"Content-Type": "text/plain"}, timeout=5)
        print(f"    [ESP32] Sent {len(devices)} devices + lists")
    except Exception as e:
        print(f"    [ESP32] Error: {e}")


def send_pending_to_esp32(device):
    try:
        requests.post(f"http://{ESP32_IP}/pending",
                      params={"mac": device["mac"],
                              "name": device["name"],
                              "ip": device["ip"]},
                      timeout=5)
        print(f"    [ESP32] Pending sent: {device['name']}")
    except Exception:
        print(f"    [ESP32] Pending error")


def notify_esp32_of_telegram_decision(mac, action):
    try:
        requests.post(f"http://{ESP32_IP}/telegram_decision",
                      data=f"{action}:{mac}",
                      headers={"Content-Type": "text/plain"}, timeout=5)
    except Exception:
        pass


def poll_esp32_actions(session):
    try:
        r = requests.get(f"http://{ESP32_IP}/esp32_action", timeout=3)
        body = r.text.strip()
        if not body:
            return

        print(f"    [ESP32] Actions:\n{body}")

        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue

            # ===== ACCEPT:MAC =====
            if line.startswith("ACCEPT:"):
                mac = line[len("ACCEPT:"):].strip().upper()
                print(f"    [ESP32] ACCEPT: {mac}")
                result = accept_mac_on_router(session, mac)
                print(f"    [Router] {result}")
                send_sms(ADMIN_PHONE, f"تم قبول الجهاز\nMAC: {mac}")
                finalize_pending(mac, "accept")

            # ===== BLOCK:MAC =====
            elif line.startswith("BLOCK:"):
                mac = line[len("BLOCK:"):].strip().upper()
                print(f"    [ESP32] BLOCK: {mac}")
                result = block_mac_on_router(session, mac)
                print(f"    [Router] {result}")
                send_sms(ADMIN_PHONE, f"تم حظر الجهاز\nMAC: {mac}")
                finalize_pending(mac, "block")

            # ===== DELETE:whitelist:MAC =====
            elif line.startswith("DELETE:"):
                rest = line[len("DELETE:"):]
                if ":" in rest:
                    list_type, mac = rest.split(":", 1)
                    mac = mac.strip().upper()
                    if list_type == "whitelist":
                        delete_from_whitelist(session, mac)
                    elif list_type == "blacklist":
                        delete_from_blacklist(session, mac)
                    print(f"    [ESP32] DELETE {list_type}: {mac}")

    except Exception as e:
        print(f"    [ESP32 Actions Error] {e}")

def finalize_pending(mac, action):
    """يزيل من pending + يُحدّث رسالة Telegram"""
    pending = load_pending()
    if mac in pending:
        msg_id = pending[mac].get("message_id")
        if msg_id:
            icon = "✅" if action == "accept" else "⛔"
            status = "تم القبول" if action == "accept" else "تم الحظر"
            name = pending[mac].get('name', 'Unknown')
            ip = pending[mac].get('ip', '')

            new_text = (
                f"{icon} <b>{status}</b>\n"
                f"<b>الاسم:</b> {name}\n"
                f"<b>MAC:</b> <code>{mac}</code>\n"
                f"<b>IP:</b> <code>{ip}</code>\n\n"
                f"<i>تم القرار من الشاشة المحلية</i>"
            )
            edit_decision_message(msg_id, new_text)
            print(f"    [Telegram] Message updated for {mac}")

        del pending[mac]
        save_pending(pending)
        print(f"    [Pending] Removed {mac}")

# =====================================================
#  Telegram
# =====================================================

def check_telegram(session):
    global LAST_UPDATE_ID

    url = f"https://api.telegram.org/bot{telegram_bot.TOKEN}/getUpdates"
    params = {"timeout": 1}
    if LAST_UPDATE_ID:
        params["offset"] = LAST_UPDATE_ID

    try:
        r = requests.get(url, params=params, timeout=3)
        data = r.json()
        if not data.get("ok"):
            return

        for update in data.get("result", []):
            LAST_UPDATE_ID = update["update_id"] + 1

            if "callback_query" in update:
                cb = update["callback_query"]
                cb_data = cb["data"]

                if cb_data.startswith("accept:") or cb_data.startswith("block:"):
                    process_decision(cb_data, cb["message"]["message_id"], cb["id"])
                    parts = cb_data.split(":", 1)
                    if len(parts) == 2:
                        notify_esp32_of_telegram_decision(parts[1], parts[0])

                elif cb_data.startswith("settings_") or \
                     cb_data.startswith("wl_") or \
                     cb_data.startswith("bl_"):
                    handle_settings_callback(
                        cb, session,
                        fetch_router_lists,
                        delete_from_whitelist,
                        delete_from_blacklist,
                        block_mac_on_router,
                        accept_mac_on_router,
                        get_connected_devices,
                        load_names
                    )

            elif "message" in update:
                msg = update["message"]
                text = msg.get("text", "")
                if text == "⚙️ الإعدادات":
                    send_settings_menu()

    except Exception:
        pass


def init_telegram_offset():
    global LAST_UPDATE_ID
    url = f"https://api.telegram.org/bot{telegram_bot.TOKEN}/getUpdates"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("ok") and data.get("result"):
            LAST_UPDATE_ID = data["result"][-1]["update_id"] + 1
    except Exception:
        pass


# =====================================================
#  Notify New Devices
# =====================================================

def notify_new_devices(new_devices):
    for d in new_devices:
        send_pending_to_esp32(d)
        msg = f"جهاز جديد!\nالاسم: {d['name']}\nMAC: {d['mac']}\nIP: {d['ip']}"
        send_sms(ADMIN_PHONE, msg)
        message_id = send_device_alert(d)
        if message_id:
            pending = load_pending()
            if d["mac"] in pending:
                pending[d["mac"]]["message_id"] = message_id
                save_pending(pending)
        time.sleep(2)


# =====================================================
#  Apply Decisions
# =====================================================

def apply_pending_decisions(session):
    decisions = load_decisions()
    pending = load_pending()
    applied = 0
    for mac, action in list(decisions.items()):
        if mac in pending:
            if action == "accept":
                accept_mac_on_router(session, mac)
            elif action == "block":
                block_mac_on_router(session, mac)
            del pending[mac]
            del decisions[mac]
            applied += 1
    if applied:
        save_pending(pending)
        save_decisions(decisions)
    return applied


# =====================================================
#  Startup Sync
# =====================================================

def startup_sync():
    print("\n" + "=" * 55)
    print("    Startup Sync")
    print("=" * 55)
    
    # ← تصفير الطلبات عند كل تشغيل
    save_pending({})
    save_decisions({})
    print("    [Reset] Pending + Decisions cleared")
    
    session = login_session()
    if not session:
        print("    FAILED: could not login.")
        return False
    print("    Login OK.")
    sync_router_lists(session)
    return True

# =====================================================
#  Check Cycle
# =====================================================

def check_devices_once():
    print("\n" + "=" * 55)
    print(f"    Check at {time.strftime('%H:%M:%S')}")
    print("=" * 55)

    session = login_session()
    if not session:
        print("    FAILED: login.")
        return

    sync_router_lists(session)

    devices = get_connected_devices(session)
    print(f"    Total: {len(devices)}")

    # حفظ أسماء الأجهزة
    update_names_from_devices(devices)

    bl, wl = fetch_router_lists(session)
    pending = load_pending()

    new_devices = [
        d for d in devices
        if d["mac"] not in wl
        and d["mac"] not in bl
        and d["mac"] not in pending
    ]

    print(f"    WL:{len(wl)} | BL:{len(bl)} | Pending:{len(pending)} | New:{len(new_devices)}")

    send_to_esp32(devices, wl, bl)

    if not new_devices:
        return

    for d in new_devices:
        pending[d["mac"]] = d
    save_pending(pending)

    notify_new_devices(new_devices)


# =====================================================
#  Main Loop
# =====================================================

def main():
    print("=" * 55)
    print("     IoT Guard - Main Controller")
    print("=" * 55)

    if not startup_sync():
        return

    init_telegram_offset()
    send_permanent_keyboard()

    last_check = 0

    while True:
        try:
            session = login_session()

            if session:
                check_telegram(session)
                poll_esp32_actions(session)

            now = time.time()
            if now - last_check >= CHECK_INTERVAL:
                check_devices_once()
                last_check = now

            time.sleep(LOOP_INTERVAL)

        except KeyboardInterrupt:
            print("\n    Stopped.")
            break
        except Exception as e:
            print(f"    Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()