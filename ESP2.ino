// =====================================================
//  IoT Guard - ESP32 #2 (Monitor + Approval)
//  LCD 16×2 + Accept/Block Buttons + IDS Monitor Mode
// =====================================================

// ============ المكتبات ============
#include <WiFi.h>              // للاتصال بالواي فاي (للإشعار ESP32 #1)
#include <WebServer.h>         // HTTP لإرسال إشعار Ready
#include <LiquidCrystal.h>     // شاشة LCD
#include <esp_wifi.h>          // للـ Monitor Mode
#include <HTTPClient.h>
// ============ بيانات الواي فاي (نفس شبكة ESP32 #1) ============
const char* ssid = "Ecs10";
const char* password = "770101712";

// ============ عنوان ESP32 #1 ============
const char* ESP1_IP = "192.168.8.181";

// ============ LCD 16×2 ============
// RS, E, D4, D5, D6, D7
LiquidCrystal lcd1(15, 4, 5, 18, 19, 21);

// ============ الأزرار ============
#define BTN_ACCEPT 22     // زر الموافقة
#define BTN_BLOCK  23     // زر الحظر

// ============ Serial مع ESP32 #1 ============
// RX2 = GPIO 16، TX2 = GPIO 17
#define SERIAL_TO_1 Serial2

// ============ LED أزرق ============
#define LED_BLUE 27       // ON عند تشغيل ESP32 #2

// ============ حالة Pending ============
bool pendingActive = false;   // هل يوجد جهاز ينتظر قرار؟
String pendingMac  = "";
String pendingName = "";
String pendingIp   = "";

// ============ حالة الهجوم ============
bool attackActive = false;
String attackType = "";
String attackMac  = "";

// ============ عدادات الهجمات (للـ Monitor Mode) ============
int deauthCount = 0;
int beaconCount = 0;
int probeCount  = 0;
unsigned long lastAttackCheck = 0;

// ============ الشبكة ============
WebServer server(80);
bool wifiReady = false;

// =====================================================
//  Monitor Mode — Sniffer Callback
// =====================================================

// تُستدعى هذه الدالة عند استقبال أي إطار Wi-Fi
void sniffer_callback(void* buf, wifi_promiscuous_pkt_type_t type) {
    wifi_promiscuous_pkt_t* pkt = (wifi_promiscuous_pkt_t*)buf;
    uint8_t* payload = pkt->payload;

    if (type != WIFI_PKT_MGMT) return;   // نهتم فقط بإطارات الإدارة

    uint8_t frame_type    = (payload[0] >> 2) & 0x3;
    uint8_t frame_subtype = (payload[0] >> 4) & 0xF;

    // ---- Deauth Frame (Management - Subtype 12) ----
    if (frame_type == 0 && frame_subtype == 12) {
        deauthCount++;
    }

    // ---- Beacon Frame (Management - Subtype 8) ----
    else if (frame_type == 0 && frame_subtype == 8) {
        beaconCount++;
    }

    // ---- Probe Request (Management - Subtype 4) ----
    else if (frame_type == 0 && frame_subtype == 4) {
        probeCount++;
    }
}

// =====================================================
//  أدوات LCD
// =====================================================

void lcdPrint(int row, int col, String text) {
    lcd1.setCursor(col, row);
    lcd1.print(text);
}

// عرض رسالة قصيرة
void showMessage(String l1, String l2) {
    lcd1.clear();
    lcdPrint(0, 0, l1);
    lcdPrint(1, 0, l2);
}

// =====================================================
//  الشاشات
// =====================================================

// شاشة الاستعداد
void showIdle() {
    lcd1.clear();
    lcdPrint(0, 0, "IoT Guard #2");
    lcdPrint(1, 0, "Monitoring...");
}

// شاشة جهاز جديد
void showPending() {
    lcd1.clear();
    lcdPrint(0, 0, pendingName.substring(0, 16));
    lcdPrint(1, 0, "ACCEPT / BLOCK");
}

// شاشة هجوم
void showAttack() {
    lcd1.clear();
    lcdPrint(0, 0, "!! ATTACK !!");
    lcdPrint(1, 0, attackType.substring(0, 16));
}

// =====================================================
//  إرسال أمر لـ ESP32 #1
// =====================================================

void sendToESP1(String msg) {
    SERIAL_TO_1.println(msg);
    Serial.print("[To #1] ");
    Serial.println(msg);
}

// =====================================================
//  إبلاغ ESP32 #1 بجاهزيتنا (HTTP)
// =====================================================

void notifyESP1Ready() {
    if (!wifiReady) return;
    HTTPClient http;
    String url = "http://" + String(ESP1_IP) + "/esp2_ready";
    http.begin(url);
    http.POST("");
    http.end();
    Serial.println("[HTTP] Sent ready to #1");
}

// =====================================================
//  إبلاغ ESP32 #1 بحدوث هجوم (HTTP)
// =====================================================

void notifyESP1Attack(String type, String mac) {
    if (!wifiReady) return;
    HTTPClient http;
    String url = "http://" + String(ESP1_IP) + "/attack?type=" + type + "&mac=" + mac;
    http.begin(url);
    http.POST("");
    http.end();
    Serial.println("[HTTP] Sent attack to #1");
}

// =====================================================
//  HTTP Handlers
// =====================================================

// استقبال جهاز جديد من ESP32 #1
void handlePending() {
    pendingMac  = server.arg("mac");
    pendingName = server.arg("name");
    pendingIp   = server.arg("ip");
    pendingActive = true;

    Serial.printf("[HTTP] Pending: %s\n", pendingName.c_str());
    showPending();
    server.send(200, "text/plain", "OK");
}

void handleRoot() {
    server.send(200, "text/plain", "ESP32 #2 Ready");
}

// =====================================================
//  Setup
// =====================================================

void setup() {
    Serial.begin(115200);
    delay(1000);

    // ===== LED أزرق ON =====
    pinMode(LED_BLUE, OUTPUT);
    digitalWrite(LED_BLUE, HIGH);

    // ===== LCD =====
    lcd1.begin(16, 2);
    showMessage("ESP32 #2", "Starting...");

    // ===== الأزرار =====
    pinMode(BTN_ACCEPT, INPUT_PULLUP);
    pinMode(BTN_BLOCK,  INPUT_PULLUP);

    // ===== Serial مع #1 =====
    SERIAL_TO_1.begin(115200, SERIAL_8N1, 16, 17);

    // ===== WiFi =====
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    showMessage("Connecting", "WiFi...");
    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 10000) {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiReady = true;
        Serial.print("\n[WiFi] IP: ");
        Serial.println(WiFi.localIP());
        showMessage("WiFi OK", WiFi.localIP().toString());
        delay(1500);

        // إبلاغ #1 بجاهزيتنا
        notifyESP1Ready();

        // إيقاف WiFi والانتقال لـ Monitor Mode
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        delay(500);
    } else {
        Serial.println("\n[WiFi] Failed");
        showMessage("WiFi Failed", "Monitor Only");
        delay(1500);
    }

    // ===== Monitor Mode =====
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_promiscuous_rx_cb(&sniffer_callback);
    esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);   // قناة شبكتك

    Serial.println("[IDS] Monitor Mode on Channel 6");

    // ===== HTTP Server (يستقبل pending من #1) =====
    // ملاحظة: بعد إيقاف WiFi، الخادم لن يعمل
    // لكن نبقيه في حالة إعادة التشغيل
    server.on("/", handleRoot);
    server.begin();

    // ===== شاشة الاستعداد =====
    showIdle();
}

// =====================================================
//  Loop
// =====================================================

void loop() {
    // ===== قراءة من ESP32 #1 =====
    if (SERIAL_TO_1.available()) {
        String msg = SERIAL_TO_1.readStringUntil('\n');
        msg.trim();
        Serial.print("[From #1] ");
        Serial.println(msg);

        // أمر لجهاز جديد
        if (msg.startsWith("PENDING|")) {
            int p1 = msg.indexOf('|', 8);
            int p2 = msg.indexOf('|', p1 + 1);
            if (p1 > 0 && p2 > 0) {
                pendingMac  = msg.substring(8, p1);
                pendingName = msg.substring(p1 + 1, p2);
                pendingIp   = msg.substring(p2 + 1);
                pendingActive = true;
                showPending();
            }
        }
        // أمر هجوم
        else if (msg.startsWith("ATTACK:")) {
            attackType = msg.substring(7);
            attackActive = true;
            showAttack();
        }
        // إلغاء الهجوم
        else if (msg == "ATTACK_CLEAR") {
            attackActive = false;
            showIdle();
        }
    }

    // ===== الأزرار =====
    static unsigned long lastPress = 0;
    if (millis() - lastPress > 300) {

        // وضع Pending: القبول/الحظر
        if (pendingActive) {
            if (digitalRead(BTN_ACCEPT) == LOW) {
                sendToESP1("ESP2_ACCEPT|" + pendingMac);
                pendingActive = false;
                showMessage("SENT", "ACCEPTED");
                delay(1200);
                showIdle();
                lastPress = millis();
            }
            else if (digitalRead(BTN_BLOCK) == LOW) {
                sendToESP1("ESP2_BLOCK|" + pendingMac);
                pendingActive = false;
                showMessage("SENT", "BLOCKED");
                delay(1200);
                showIdle();
                lastPress = millis();
            }
        }
        // وضع هجوم: زر القبول = "رأيت التنبيه"
        else if (attackActive) {
            if (digitalRead(BTN_ACCEPT) == LOW) {
                sendToESP1("ATTACK_ACK");
                attackActive = false;
                showIdle();
                lastPress = millis();
            }
        }
    }

    // ===== فحص الهجمات (كل 5 ثوان) =====
    if (millis() - lastAttackCheck > 5000) {
        lastAttackCheck = millis();

        // ---- Deauth Attack ----
        if (deauthCount > 20) {
            Serial.printf("[IDS] Deauth Attack! (%d frames)\n", deauthCount);
            notifyESP1Attack("DEAUTH", "unknown");
            attackActive = true;
            attackType = "DEAUTH";
            showAttack();
        }

        // ---- Beacon Flood ----
        else if (beaconCount > 100) {
            Serial.printf("[IDS] Beacon Flood! (%d frames)\n", beaconCount);
            notifyESP1Attack("BEACON_FLOOD", "unknown");
            attackActive = true;
            attackType = "BEACON";
            showAttack();
        }

        // ---- Probe Flood ----
        else if (probeCount > 200) {
            Serial.printf("[IDS] Probe Flood! (%d frames)\n", probeCount);
            notifyESP1Attack("PROBE_FLOOD", "unknown");
            attackActive = true;
            attackType = "PROBE";
            showAttack();
        }

        // تصفير العدادات
        deauthCount = 0;
        beaconCount = 0;
        probeCount  = 0;
    }

    delay(20);
}