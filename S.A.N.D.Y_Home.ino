#include <Servo.h>

// --- PIN DEFINITIONS ---
#define LED_HALL    D1  
#define LED_BEDROOM D2  
#define SERVO_PIN   D7  
#define BUZZER_PIN  D8  
#define GAS_PIN     A0  

Servo doorServo;
const int GAS_THRESHOLD = 600;

void setup() {
  // Start USB Communication
  Serial.begin(115200);

  pinMode(LED_HALL, OUTPUT);
  pinMode(LED_BEDROOM, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  
  doorServo.attach(SERVO_PIN);
  doorServo.write(0); // Start Door Closed

  // Flash LED to show we are ready
  digitalWrite(LED_HALL, HIGH); delay(200); digitalWrite(LED_HALL, LOW);
}

void loop() {
  // 1. LISTEN FOR COMMANDS FROM PYTHON
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove spaces

    if (command == "on") {
      digitalWrite(LED_HALL, HIGH);
      digitalWrite(LED_BEDROOM, HIGH);
      Serial.println("Lights ON");
    }
    else if (command == "off") {
      digitalWrite(LED_HALL, LOW);
      digitalWrite(LED_BEDROOM, LOW);
      Serial.println("Lights OFF");
    }
    else if (command == "door-open") {
      doorServo.write(180);
      Serial.println("Door Opened");
    }
    else if (command == "door-close") {
      doorServo.write(0);
      Serial.println("Door Closed");
    }
    else if (command == "alert") {
      // Intruder Alarm Pattern
      for(int i=0; i<5; i++){
        digitalWrite(BUZZER_PIN, HIGH); delay(50);
        digitalWrite(BUZZER_PIN, LOW); delay(50);
      }
      Serial.println("Alarm Triggered");
    }
    else if (command == "status") {
      // MANUALLY BUILD JSON STRING (No Library Needed)
      int gas = analogRead(GAS_PIN);
      String door = (doorServo.read() > 10) ? "OPEN" : "CLOSED";
      String hall = (digitalRead(LED_HALL) == HIGH) ? "ON" : "OFF";
      String bed = (digitalRead(LED_BEDROOM) == HIGH) ? "ON" : "OFF";
      
      String json = "{";
      json += "\"gas\": " + String(gas) + ",";
      json += "\"door\": \"" + door + "\",";
      json += "\"hall\": \"" + hall + "\",";
      json += "\"bedroom\": \"" + bed + "\"";
      json += "}";
      
      Serial.println(json);
    }
  }

  // 2. AUTOMATIC GAS SAFETY CHECK
  int gasValue = analogRead(GAS_PIN);
  if (gasValue > GAS_THRESHOLD) {
    // Continuous Beep for Danger
    digitalWrite(BUZZER_PIN, HIGH); delay(100);
    digitalWrite(BUZZER_PIN, LOW); delay(100);
  }
}