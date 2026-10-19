# =====================================================
#  SMS Sender via ADB (يدعم العربية والإنجليزية)
# =====================================================

import subprocess
import time
import base64


# نص يُضاف في نهاية كل رسالة
FOOTER = "\n\nيرجى فتح تطبيق تيليجرام للمراجعة"


def send_sms(phone_number, message_body):
    """
    يرسل SMS عبر ADB
    - phone_number: رقم المستقبل
    - message_body: نص الرسالة (عربي أو إنجليزي)
    """
    # إضافة التذييل تلقائيًا
    full_message = message_body + FOOTER
    
    clean_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    # 1. فتح تطبيق الرسائل
    subprocess.run(
        f'adb shell am start -a android.intent.action.SENDTO '
        f'-d "sms:{clean_number}" com.samsung.android.messaging',
        shell=True, capture_output=True
    )
    time.sleep(2)
    
    # 2. تحويل النص إلى Base64
    b64 = base64.b64encode(full_message.encode('utf-8')).decode('ascii')
    
    # 3. إرسال النص
    subprocess.run(
        f'adb shell am broadcast -a ADB_INPUT_B64 --es msg "{b64}"',
        shell=True, capture_output=True
    )
    time.sleep(1.5)
    
    # 4. إخفاء الكيبورد
    subprocess.run("adb shell input keyevent 4", shell=True, capture_output=True)
    time.sleep(0.5)
    
    # 5. الإرسال
    subprocess.run("adb shell input tap 90 2200", shell=True, capture_output=True)
    time.sleep(1)
    
    print(f"[SMS] Sent to {phone_number}")


def notify_new_device(name, mac, ip):
    """إشعار جهاز جديد"""
    msg = f"جهاز جديد!\nالاسم: {name}\nMAC: {mac}\nIP: {ip}"
    send_sms("776723322", msg)


def notify_attack(name, mac, attack_type):
    """إشعار هجوم"""
    msg = f"تحذير: هجوم!\nالنوع: {attack_type}\nالجهاز: {name}\nMAC: {mac}"
    send_sms("776723322", msg)


# للاختبار
if __name__ == "__main__":
    print("=== Test 1: New Device ===")
    notify_new_device("Galaxy-S21", "AA:BB:CC:DD:EE:FF", "192.168.8.121")
    
    time.sleep(5)
    
    print("=== Test 2: Attack ===")
    notify_attack("Unknown-Device", "11:22:33:44:55:66", "ARP Spoofing")