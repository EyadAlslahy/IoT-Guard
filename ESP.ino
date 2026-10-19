





#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <LiquidCrystal.h>
#include <ESPmDNS.h>
#include <stdint.h>



const char* ssid = "Ecs10";
const char* password = "770101712";


const char* tb_server = "thingsboard.cloud";
const int tb_port = 1883;
const char* tb_token = "t66t6XtL63n3y0swtWmz";



LiquidCrystal lcd(4, 5, 15, 18, 19, 21);


#define BUZZER 26
#define RELAY 22
#define BTN_BACK 13
#define BTN_UP 14
#define BTN_DOWN 12
#define BTN_SELECT 39


#define LED_RED 32
#define LED_YELLOW 33
#define LED_GREEN 25
#define LED_BLUE 27



#define SERIAL_2 Serial2


uint16_t KEY[5] = { 0x0123, 0x4567, 0x89AB, 0xCDEF, 0x0123 };
uint32_t NONCE = 0xDEADBEEF;


String dev_macs[20];
String dev_names[20];
String dev_ips[20];
int totalDevices = 0;


String whitelist[20];
int totalWhite = 0;
String blacklist[20];
int totalBlack = 0;


enum Screen { SCR_DEVICES,
              SCR_MENU,
              SCR_WHITE,
              SCR_BLACK,
              SCR_CONFIRM };
Screen currentScreen = SCR_DEVICES;

int idxDevice = 0;
int idxMenu = 0;
int idxWhite = 0;
int idxBlack = 0;


bool pendingActive = false;
String pendingMac = "";
String pendingName = "";
String pendingIp = "";


bool attackActive = false;
String attackType = "";
String attackMac = "";


bool ledBlinkState = false;
unsigned long lastBlink = 0;
bool esp32_2_ready = false;


String actionQueue = "";


unsigned long lastDeviceChange = 0;
unsigned long buzzerTimer = 0;

WebServer server(80);
WiFiClient espClient;
PubSubClient mqtt(espClient);





static const uint8_t SBOX[16] = {
  0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD, 0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2
};

uint64_t apply_sbox(uint64_t s) {
  uint64_t r = 0;
  for (int i = 0; i < 16; i++) {
    uint8_t n = (s >> (i * 4)) & 0xF;
    r |= ((uint64_t)SBOX[n]) << (i * 4);
  }
  return r;
}

static const uint8_t PBOX[64] = {
  0, 16, 32, 48, 1, 17, 33, 49, 2, 18, 34, 50, 3, 19, 35, 51,
  4, 20, 36, 52, 5, 21, 37, 53, 6, 22, 38, 54, 7, 23, 39, 55,
  8, 24, 40, 56, 9, 25, 41, 57, 10, 26, 42, 58, 11, 27, 43, 59,
  12, 28, 44, 60, 13, 29, 45, 61, 14, 30, 46, 62, 15, 31, 47, 63
};

uint64_t apply_pbox(uint64_t s) {
  uint64_t r = 0;
  for (int i = 0; i < 64; i++)
    if ((s >> i) & 1) r |= (1ULL << PBOX[i]);
  return r;
}

void rot_left_1(uint16_t k[5]) {
  uint16_t c = (k[0] >> 15) & 1;
  k[0] = ((k[0] << 1) | (k[1] >> 15)) & 0xFFFF;
  k[1] = ((k[1] << 1) | (k[2] >> 15)) & 0xFFFF;
  k[2] = ((k[2] << 1) | (k[3] >> 15)) & 0xFFFF;
  k[3] = ((k[3] << 1) | (k[4] >> 15)) & 0xFFFF;
  k[4] = ((k[4] << 1) | c) & 0xFFFF;
}

void generate_round_keys(uint16_t key[5], uint64_t rk[32]) {
  uint16_t k[5];
  for (int i = 0; i < 5; i++) k[i] = key[i];
  rk[0] = ((uint64_t)k[0] << 48) | ((uint64_t)k[1] << 32) | ((uint64_t)k[2] << 16) | ((uint64_t)k[3]);
  for (int r = 1; r <= 31; r++) {
    for (int i = 0; i < 61; i++) rot_left_1(k);
    uint8_t tn = (k[0] >> 12) & 0xF;
    k[0] = (k[0] & 0x0FFF) | ((uint16_t)SBOX[tn] << 12);
    k[3] ^= (r >> 1) & 0xF;
    k[4] ^= (r & 1) << 15;
    rk[r] = ((uint64_t)k[0] << 48) | ((uint64_t)k[1] << 32) | ((uint64_t)k[2] << 16) | ((uint64_t)k[3]);
  }
}

uint64_t present_encrypt(uint64_t pt, uint16_t key[5]) {
  uint64_t rk[32];
  generate_round_keys(key, rk);
  uint64_t s = pt ^ rk[0];
  for (int r = 1; r <= 31; r++) {
    s = apply_sbox(s);
    s = apply_pbox(s);
    s ^= rk[r];
  }
  return s;
}

String present_ctr_decrypt(uint8_t* cipher, int len, uint32_t nonce) {
  String result = "";
  uint32_t counter = 0;
  for (int i = 0; i < len; i += 8) {
    uint64_t cb = ((uint64_t)nonce << 32) | counter;
    uint64_t ks = present_encrypt(cb, KEY);
    int chunk = (len - i < 8) ? (len - i) : 8;
    for (int j = 0; j < chunk; j++) {
      uint8_t ks_b = (ks >> ((7 - j) * 8)) & 0xFF;
      result += (char)(cipher[i + j] ^ ks_b);
    }
    counter++;
  }
  return result;
}

String present_ctr_encrypt(String plaintext, uint32_t nonce) {
  String hex_out = "";
  uint32_t counter = 0;
  int len = plaintext.length();

  for (int i = 0; i < len; i += 8) {
    uint64_t cb = ((uint64_t)nonce << 32) | counter;
    uint64_t ks = present_encrypt(cb, KEY);
    for (int j = 0; j < 8 && (i + j) < len; j++) {
      uint8_t ks_b = (ks >> ((7 - j) * 8)) & 0xFF;
      uint8_t enc_b = plaintext[i + j] ^ ks_b;
      char hex[3];
      sprintf(hex, "%02X", enc_b);
      hex_out += hex;
    }
    counter++;
  }
  return hex_out;
}

int hex_to_bytes(String hex, uint8_t* out, int max_len) {
  int n = hex.length() / 2;
  if (n > max_len) n = max_len;
  for (int i = 0; i < n; i++) {
    String byte_str = hex.substring(i * 2, i * 2 + 2);
    out[i] = (uint8_t)strtol(byte_str.c_str(), NULL, 16);
  }
  return n;
}






void lcdPrint(int row, int col, String text) {
  lcd.setCursor(col, row);
  lcd.print(text);
}


void lcdClearRow(int row) {
  lcd.setCursor(0, row);
  lcd.print("                    ");
}


String compressMAC(String mac) {
  mac.remove(2, 1);
  return mac;
}






void showDevices() {
  lcd.clear();
  if (totalDevices == 0) {
    lcdPrint(0, 0, "No devices");
    lcdPrint(1, 0, "Waiting...");
    lcdPrint(3, 0, "BACK PREV NEXT MENU");
    return;
  }


  String name = dev_names[idxDevice];
  if (name.length() > 20) name = name.substring(0, 20);
  lcdPrint(0, 0, name);


  lcdPrint(1, 0, dev_ips[idxDevice]);


  lcdPrint(2, 0, compressMAC(dev_macs[idxDevice]));


  lcdPrint(3, 0, "BACK PREV NEXT MENU");
}


void showMenu() {
  lcd.clear();


  if (idxMenu == 0) lcdPrint(0, 0, ">Connected Devices");
  else lcdPrint(0, 0, " Connected Devices");


  if (idxMenu == 1) lcdPrint(1, 0, ">Whitelist");
  else lcdPrint(1, 0, " Whitelist");


  if (idxMenu == 2) lcdPrint(2, 0, ">Blacklist");
  else lcdPrint(2, 0, " Blacklist");


  lcdPrint(3, 0, "BACK UP DOWN OPEN");
}


void showWhite() {
  lcd.clear();
  if (totalWhite == 0) {
    lcdPrint(0, 0, "Whitelist Empty");
    lcdPrint(3, 0, "BACK UP DOWN DEL");
    return;
  }


  for (int row = 0; row < 3; row++) {
    int i = idxWhite + row - 1;
    if (i < 0 || i >= totalWhite) continue;


    String prefix = (i == idxWhite) ? ">" : " ";

    String mac = whitelist[i];
    if (mac.length() > 14) mac = mac.substring(0, 14);
    String line = prefix + mac;
    while (line.length() < 15) line += " ";
    line += "[DEL]";
    lcdPrint(row, 0, line);
  }

  lcdPrint(3, 0, "BACK UP DOWN DEL");
}


void showBlack() {
  lcd.clear();
  if (totalBlack == 0) {
    lcdPrint(0, 0, "Blacklist Empty");
    lcdPrint(3, 0, "BACK UP DOWN DEL");
    return;
  }

  for (int row = 0; row < 3; row++) {
    int i = idxBlack + row - 1;
    if (i < 0 || i >= totalBlack) continue;

    String prefix = (i == idxBlack) ? ">" : " ";
    String mac = blacklist[i];
    if (mac.length() > 14) mac = mac.substring(0, 14);
    String line = prefix + mac;
    while (line.length() < 15) line += " ";
    line += "[DEL]";
    lcdPrint(row, 0, line);
  }

  lcdPrint(3, 0, "BACK UP DOWN DEL");
}


void showConfirm(String deviceMac, bool isWhite) {
  lcd.clear();
  lcdPrint(0, 0, "Delete this MAC?");
  lcdPrint(1, 0, deviceMac.substring(0, 20));
  lcdPrint(3, 0, "    NO    YES    ");
}


void showPending() {
  lcd.clear();
  lcdPrint(0, 0, "New Device!");
  lcdPrint(1, 0, pendingName.substring(0, 20));
  lcdPrint(2, 0, compressMAC(pendingMac).substring(0, 20));
  lcdPrint(3, 0, "NO(YES)    YES     ");
}



void showCurrentScreen() {
  switch (currentScreen) {
    case SCR_DEVICES: showDevices(); break;
    case SCR_MENU: showMenu(); break;
    case SCR_WHITE: showWhite(); break;
    case SCR_BLACK: showBlack(); break;
    default: break;
  }
}






void handleData() {
  if (!server.hasArg("plain")) {
    server.send(400, "text/plain", "No body");
    return;
  }
  String body = server.arg("plain");
  Serial.println("[HTTP] Received data");









  totalDevices = 0;
  totalWhite = 0;
  totalBlack = 0;

  int section = 0;
  int start = 0;

  while (start < body.length()) {
    int nl = body.indexOf('\n', start);
    if (nl == -1) nl = body.length();
    String line = body.substring(start, nl);
    line.trim();

    if (line == "DEVICES") {
      section = 0;
    } else if (line == "WHITELIST") {
      section = 1;
    } else if (line == "BLACKLIST") {
      section = 2;
    } else if (line.length() > 0) {
      if (section == 0 && totalDevices < 20) {

        uint8_t bytes[256];
        int n = hex_to_bytes(line, bytes, 256);
        String dec = present_ctr_decrypt(bytes, n, NONCE);

        int sep1 = dec.indexOf('|');
        int sep2 = dec.indexOf('|', sep1 + 1);
        if (sep1 > 0 && sep2 > 0) {
          dev_macs[totalDevices] = dec.substring(0, sep1);
          dev_names[totalDevices] = dec.substring(sep1 + 1, sep2);
          dev_ips[totalDevices] = dec.substring(sep2 + 1);
          totalDevices++;
        }
      } else if (section == 1 && totalWhite < 20) {
        whitelist[totalWhite++] = line;
      } else if (section == 2 && totalBlack < 20) {
        blacklist[totalBlack++] = line;
      }
    }
    start = nl + 1;
  }

  Serial.printf("[HTTP] Devices:%d White:%d Black:%d\n",
                totalDevices, totalWhite, totalBlack);


  if (idxDevice >= totalDevices) idxDevice = 0;
  if (idxWhite >= totalWhite) idxWhite = 0;
  if (idxBlack >= totalBlack) idxBlack = 0;

  showCurrentScreen();
  server.send(200, "text/plain", "OK");
}



void handlePending() {
  String mac = server.arg("mac");
  String name = server.arg("name");
  String ip = server.arg("ip");

  if (mac.length() == 0) {
    server.send(400, "text/plain", "Missing mac");
    return;
  }

  pendingMac = mac;
  pendingName = name;
  pendingIp = ip;
  pendingActive = true;


  SERIAL_2.println("PENDING|" + mac + "|" + name + "|" + ip);
  Serial.printf("[To #2] PENDING: %s\n", name.c_str());




  tone(BUZZER, 2000, 300);
  server.send(200, "text/plain", "OK");
}



void handleTelegramDecision() {
  String decision = server.arg("plain");
  Serial.printf("[HTTP] Telegram decision: %s\n", decision.c_str());


  SERIAL_2.println("CLEAR_PENDING");

  if (pendingActive) {
    pendingActive = false;
    noTone(BUZZER);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_RED, LOW);

    String action = decision.startsWith("accept") ? "ACCEPTED" : "BLOCKED";
    lcd.clear();
    lcdPrint(0, 0, "Decision from");
    lcdPrint(1, 0, "Telegram: " + action);
    delay(2000);
    showCurrentScreen();
  }

  server.send(200, "text/plain", "OK");
}

void handleEsp32Action() {
  if (actionQueue.length() > 0) {
    server.send(200, "text/plain", actionQueue);
    Serial.printf("[HTTP] Sent actions: %s\n", actionQueue.c_str());
    actionQueue = "";
  } else {
    server.send(200, "text/plain", "");
  }
}


void handleAttack() {
  attackActive = true;
  attackType = server.arg("type");
  attackMac = server.arg("mac");
  Serial.printf("[HTTP] Attack: %s from %s\n", attackType.c_str(), attackMac.c_str());
  server.send(200, "text/plain", "OK");
}


void handleEsp2Ready() {
  esp32_2_ready = true;
  digitalWrite(LED_BLUE, HIGH);
  server.send(200, "text/plain", "OK");
}

void handleRoot() {
  server.send(200, "text/plain", "IoT Guard ESP32 #1");
}





void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting...");
    if (mqtt.connect("ESP32-IoTGuard", tb_token, NULL)) {
      Serial.println(" OK");
    } else {
      Serial.print(" Failed rc=");
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}





void handleButtons() {
  static unsigned long lastPress = 0;
  if (millis() - lastPress < 300) return;

  bool bBack = (digitalRead(BTN_BACK) == LOW);
  bool bUp = (digitalRead(BTN_UP) == LOW);
  bool bDown = (digitalRead(BTN_DOWN) == LOW);
  bool bSelect = (digitalRead(BTN_SELECT) == LOW);


  if (currentScreen == SCR_DEVICES) {
    if (bUp && idxDevice > 0) {
      idxDevice--;
      showDevices();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bDown && idxDevice + 1 < totalDevices) {
      idxDevice++;
      showDevices();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bSelect) {
      currentScreen = SCR_MENU;
      idxMenu = 0;
      showMenu();
      lastPress = millis();
    }
  }


  else if (currentScreen == SCR_MENU) {
    if (bUp && idxMenu > 0) {
      idxMenu--;
      showMenu();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bDown && idxMenu < 2) {
      idxMenu++;
      showMenu();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bBack) {
      currentScreen = SCR_DEVICES;
      showDevices();
      lastPress = millis();
    }
    if (bSelect) {
      if (idxMenu == 0) {
        currentScreen = SCR_DEVICES;
        showDevices();
      } else if (idxMenu == 1) {
        currentScreen = SCR_WHITE;
        idxWhite = 0;
        showWhite();
      } else if (idxMenu == 2) {
        currentScreen = SCR_BLACK;
        idxBlack = 0;
        showBlack();
      }
      lastPress = millis();
    }
  }


  else if (currentScreen == SCR_WHITE) {
    if (bUp && idxWhite > 0) {
      idxWhite--;
      showWhite();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bDown && idxWhite + 1 < totalWhite) {
      idxWhite++;
      showWhite();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bBack) {
      currentScreen = SCR_MENU;
      showMenu();
      lastPress = millis();
    }
    if (bSelect && totalWhite > 0) {
      String mac = whitelist[idxWhite];
      actionQueue += "DELETE:whitelist:" + mac + "\n";

      for (int i = idxWhite; i < totalWhite - 1; i++)
        whitelist[i] = whitelist[i + 1];
      totalWhite--;
      if (idxWhite >= totalWhite && idxWhite > 0) idxWhite--;

      tone(BUZZER, 1500, 200);
      showWhite();
      lastPress = millis();
    }
  }


  else if (currentScreen == SCR_BLACK) {
    if (bUp && idxBlack > 0) {
      idxBlack--;
      showBlack();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bDown && idxBlack + 1 < totalBlack) {
      idxBlack++;
      showBlack();
      tone(BUZZER, 1000, 50);
      lastPress = millis();
    }
    if (bBack) {
      currentScreen = SCR_MENU;
      showMenu();
      lastPress = millis();
    }
    if (bSelect && totalBlack > 0) {
      String mac = blacklist[idxBlack];
      actionQueue += "DELETE:blacklist:" + mac + "\n";

      for (int i = idxBlack; i < totalBlack - 1; i++)
        blacklist[i] = blacklist[i + 1];
      totalBlack--;
      if (idxBlack >= totalBlack && idxBlack > 0) idxBlack--;

      tone(BUZZER, 1500, 200);
      showBlack();
      lastPress = millis();
    }
  }
}




void handleLedsAndBuzzer() {

  if (millis() - lastBlink > 500) {
    lastBlink = millis();
    ledBlinkState = !ledBlinkState;


    digitalWrite(LED_RED, attackActive ? (ledBlinkState ? HIGH : LOW) : LOW);


    digitalWrite(LED_YELLOW, pendingActive ? (ledBlinkState ? HIGH : LOW) : LOW);
  }


  if (attackActive) {

    tone(BUZZER, 3000);
  } else if (pendingActive) {

    if (millis() - buzzerTimer > 1000) {
      buzzerTimer = millis();
      static bool beepOn = false;
      beepOn = !beepOn;
      if (beepOn) tone(BUZZER, 1500);
      else noTone(BUZZER);
    }
  } else {
    noTone(BUZZER);
  }
}






void readSerialFromESP2() {
  if (SERIAL_2.available()) {
    String msg = SERIAL_2.readStringUntil('\n');
    msg.trim();
    Serial.print("[From #2] ");
    Serial.println(msg);


    if (msg.startsWith("ESP2_ACCEPT|")) {
      String mac = msg.substring(12);
      actionQueue += "ACCEPT:" + mac + "\n";
      pendingActive = false;
      noTone(BUZZER);
      digitalWrite(LED_YELLOW, LOW);

      lcd.clear();
      lcdPrint(0, 0, "Accepted from");
      lcdPrint(1, 0, "#2 (Small LCD)");
      delay(1500);
      showCurrentScreen();
    }


    else if (msg.startsWith("ESP2_BLOCK|")) {
      String mac = msg.substring(11);
      actionQueue += "BLOCK:" + mac + "\n";
      pendingActive = false;
      noTone(BUZZER);
      digitalWrite(LED_YELLOW, LOW);

      lcd.clear();
      lcdPrint(0, 0, "Blocked from");
      lcdPrint(1, 0, "#2 (Small LCD)");
      delay(1500);
      showCurrentScreen();
    }


    else if (msg.startsWith("ATTACK:")) {
      String type = msg.substring(7);
      attackActive = true;
      attackType = type;
      lcd.clear();
      lcdPrint(0, 0, "!! ATTACK !!");
      lcdPrint(1, 0, type);
      tone(BUZZER, 3000);
    }


    else if (msg == "ATTACK_ACK") {
      attackActive = false;
      noTone(BUZZER);
      showCurrentScreen();
    }


    else if (msg == "READY") {
      esp32_2_ready = true;
      digitalWrite(LED_BLUE, HIGH);
    }
  }
}




void autoChangeDevice() {
  if (currentScreen != SCR_DEVICES) return;
  if (pendingActive) return;
  if (totalDevices <= 1) return;

  if (millis() - lastDeviceChange > 5000) {
    lastDeviceChange = millis();
    idxDevice = (idxDevice + 1) % totalDevices;
    showDevices();
  }
}





void setup() {
  Serial.begin(115200);
  delay(1000);


  SERIAL_2.begin(115200, SERIAL_8N1, 16, 17);


  lcd.begin(20, 4);


  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY, OUTPUT);
  pinMode(BTN_BACK, INPUT_PULLUP);
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  pinMode(BTN_SELECT, INPUT);

  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);


  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, LOW);


  lcd.setCursor(0, 0);
  lcd.print("IoT Guard #1");
  lcd.setCursor(0, 1);
  lcd.print("Connecting WiFi...");


  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[WiFi] Connected");
  Serial.print("[WiFi] IP: ");
  Serial.println(WiFi.localIP());


  if (MDNS.begin("iotguard")) {
    Serial.println("[mDNS] iotguard.local");
  }


  mqtt.setServer(tb_server, tb_port);
  mqtt.setBufferSize(4096);
  connectMQTT();


  server.on("/", handleRoot);
  server.on("/data", HTTP_POST, handleData);
  server.on("/pending", HTTP_POST, handlePending);
  server.on("/telegram_decision", HTTP_POST, handleTelegramDecision);
  server.on("/esp32_action", HTTP_GET, handleEsp32Action);
  server.on("/attack", HTTP_POST, handleAttack);
  server.on("/esp2_ready", HTTP_POST, handleEsp2Ready);
  server.begin();
  Serial.println("[HTTP] Server started");


  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("IoT Guard Ready");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());
  delay(2000);

  showCurrentScreen();
}





void loop() {
  server.handleClient();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  handleButtons();
  handleLedsAndBuzzer();
  readSerialFromESP2();
  autoChangeDevice();

  delay(20);
}