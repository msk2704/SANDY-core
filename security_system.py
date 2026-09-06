import cv2
import numpy as np
import os
import json
import threading
import requests
import time
from collections import deque
from twilio.rest import Client
import pyttsx3
import backend 

# --- GLOBAL CONTROL FLAGS ---
security_active = False  # <--- NEW SWITCH

def speak(text):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.say(text)
        engine.runAndWait()
    except: pass

def send_whatsapp():
    try:
        client = Client(backend.TWILIO_SID, backend.TWILIO_AUTH)
        client.messages.create(
            from_=backend.TWILIO_PHONE, 
            body="🚨 S.A.N.D.Y ALERT: Intruder Detected!", 
            to=backend.FAMILY_PHONE
        )
    except: pass

def trigger_hardware_alarm():
    try: requests.get(f"{backend.HOUSE_IP}/alert", timeout=1)
    except: pass

# --- NEW FUNCTION TO STOP CAMERA ---
def stop_camera():
    global security_active
    security_active = False
    print("LOG: Stopping Security Camera...")

def start_camera_loop():
    global security_active
    
    # Prevent starting if already running
    if security_active:
        print("Security is already active.")
        return

    security_active = True  # <--- Turn Switch ON
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    if not os.path.exists('trainer.yml'): return
    recognizer.read('trainer.yml')
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    names_dict = {}
    if os.path.exists('names.json'):
        with open('names.json') as f: names_dict = json.load(f)

    print("LOG: Opening Camera...")
    cam = cv2.VideoCapture(0)
    
    # FORCE WINDOW TO TOP
    window_name = 'S.A.N.D.Y Security Cam'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    history = deque(maxlen=15)
    intruder_timer = 0
    alarm_sent = False
    
    speak("Security Protocols Initiated.")
    
    # --- MAIN LOOP CHECKS THE SWITCH ---
    while security_active:
        ret, img = cam.read()
        if not ret: break
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)
        
        if len(faces) == 0: history.clear()

        for(x,y,w,h) in faces:
            id, conf = recognizer.predict(gray[y:y+h,x:x+w])
            
            guess = str(id) if conf < 65 else "Unknown"
            history.append(guess)
            
            final_decision = "Scanning..."
            if len(history) == 15:
                most_common = max(set(history), key=history.count)
                if history.count(most_common) > 10: final_decision = most_common

            color = (0, 255, 0)
            name = "..."
            
            if final_decision in names_dict:
                name = names_dict[final_decision]
                intruder_timer = 0
            elif final_decision == "Unknown":
                name = "INTRUDER"
                color = (0, 0, 255)
                intruder_timer += 1
            
            cv2.rectangle(img, (x,y), (x+w,y+h), color, 2)
            cv2.putText(img, name, (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            if intruder_timer > 30:
                cv2.putText(img, "ALARM!", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
                if not alarm_sent:
                    threading.Thread(target=trigger_hardware_alarm).start()
                    threading.Thread(target=send_whatsapp).start()
                    threading.Thread(target=speak, args=("Intruder detected.",)).start()
                    alarm_sent = True

        cv2.imshow(window_name, img)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    
    # CLEANUP WHEN LOOP BREAKS
    cam.release()
    cv2.destroyAllWindows()
    speak("Security Deactivated.")

if __name__ == "__main__":
    start_camera_loop()