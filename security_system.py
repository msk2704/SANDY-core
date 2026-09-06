import cv2
import os
import json
import threading
import time
from collections import deque
from twilio.rest import Client
import backend 
import pygame

# --- GLOBAL CONTROL FLAGS ---
security_active = False 

def speak_alert(text):
    """Uses the safe TTS engine from backend instead of pyttsx3"""
    try:
        audio_file = backend.generate_voice(text)
        if audio_file:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
            os.remove(audio_file)
    except Exception as e:
        print(f"Security TTS Error: {e}")

def send_whatsapp():
    try:
        client = Client(backend.TWILIO_SID, backend.TWILIO_AUTH)
        
        # Twilio requires the 'whatsapp:' prefix for WhatsApp messages
        from_whatsapp = f"whatsapp:{backend.TWILIO_PHONE}"
        to_whatsapp = f"whatsapp:{backend.FAMILY_PHONE}"
        
        client.messages.create(
            from_=from_whatsapp, 
            body="🚨 S.A.N.D.Y ALERT: Unknown person detected at the main camera!", 
            to=to_whatsapp
        )
        print("✅ WhatsApp Alert Sent.")
    except Exception as e:
        print(f"❌ WhatsApp API Failed: {e}")

def trigger_hardware_alarm():
    """Triggers the physical alarm via the USB serial connection"""
    try:
        response = backend.send_command("alert-on")
        print(f"Hardware Alarm Status: {response}")
    except Exception as e:
        print(f"Hardware Alarm Failed: {e}")

def stop_camera():
    global security_active
    security_active = False
    print("LOG: Stopping Security Camera...")

def start_camera_loop():
    global security_active
    
    if security_active:
        print("Security is already active.")
        return

    security_active = True 
    
    if not os.path.exists('trainer.yml'):
        print("❌ Error: 'trainer.yml' missing. Run train_face.py first.")
        security_active = False
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read('trainer.yml')
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    names_dict = {}
    if os.path.exists('names.json'):
        with open('names.json') as f: 
            names_dict = json.load(f)

    print("LOG: Opening Camera...")
    cam = cv2.VideoCapture(0)
    
    window_name = 'S.A.N.D.Y Security Cam'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    history = deque(maxlen=15)
    intruder_frames = 0
    alarm_sent = False
    
    threading.Thread(target=speak_alert, args=("Security Protocols Initiated.",), daemon=True).start()
    
    while security_active:
        ret, img = cam.read()
        if not ret: 
            print("Camera feed lost.")
            break
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)
        
        if len(faces) == 0: 
            history.clear()

        for(x,y,w,h) in faces:
            id, conf = recognizer.predict(gray[y:y+h,x:x+w])
            
            # Confidence threshold (lower is better in LBPH)
            guess = str(id) if conf < 65 else "Unknown"
            history.append(guess)
            
            final_decision = "Scanning..."
            if len(history) == 15:
                most_common = max(set(history), key=history.count)
                if history.count(most_common) > 10: 
                    final_decision = most_common

            color = (0, 255, 0)
            name = "..."
            
            if final_decision in names_dict:
                name = names_dict[final_decision]
                intruder_frames = 0 # Reset if known face is seen
            elif final_decision == "Unknown":
                name = "INTRUDER"
                color = (0, 0, 255)
                intruder_frames += 1
            
            cv2.rectangle(img, (x,y), (x+w,y+h), color, 2)
            cv2.putText(img, name, (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            # Trigger alarm after ~3 seconds of continuous intruder detection (assuming ~30fps)
            if intruder_frames > 90:
                cv2.putText(img, "ALARM!", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
                if not alarm_sent:
                    threading.Thread(target=trigger_hardware_alarm, daemon=True).start()
                    threading.Thread(target=send_whatsapp, daemon=True).start()
                    threading.Thread(target=speak_alert, args=("Intruder detected. Alerting family.",), daemon=True).start()
                    alarm_sent = True

        cv2.imshow(window_name, img)
        if cv2.waitKey(1) & 0xFF == ord('q'): 
            break
    
    cam.release()
    cv2.destroyAllWindows()
    threading.Thread(target=speak_alert, args=("Security Deactivated.",), daemon=True).start()

if __name__ == "__main__":
    start_camera_loop()
