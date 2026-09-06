import os
from dotenv import load_dotenv
import speech_recognition as sr
from groq import Groq
from gtts import gTTS
import httpx
import ssl
import random
import re
from datetime import datetime
import webbrowser
import threading
import serial       # <--- USB Communication Library
import time
import json
from twilio.rest import Client
import security_system

# --- 1. CONFIGURATION ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROK_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# --- USB CONNECTION SETUP (CRITICAL) ---
# CHANGE 'COM3' TO YOUR ACTUAL PORT! (Check Device Manager)
SERIAL_PORT = 'COM5' 
BAUD_RATE = 115200

try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Wait for connection to settle
    print(f"✅ USB Connection Established on {SERIAL_PORT}")
except Exception as e:
    print(f"❌ USB Connection Failed: {e}")
    arduino = None

# --- TWILIO CREDENTIALS ---
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
FAMILY_PHONE = os.getenv("FAMILY_PHONE")

MEDICINES = {
    "morning": "Blood Pressure Tablet (Amlodipine)",
    "afternoon": "Sugar Tablet (Metformin)",
    "night": "Sleeping Pill and Calcium"
}

ssl._create_default_https_context = ssl._create_unverified_context

# --- INITIALIZATION ---
try:
    unsafe_client = httpx.Client(verify=False)
    groq_client = Groq(api_key=GROQ_API_KEY, http_client=unsafe_client)
    try: twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
    except: twilio_client = None
except: pass

# --- 2. SMART FUNCTIONS ---

def transcribe_audio(audio_filepath):
    if not audio_filepath: return ""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(audio_filepath) as source:
            return r.recognize_google(r.record(source), language='en-IN').lower()
    except: return ""

def contains_hindi(text):
    if bool(re.search(r'[\u0900-\u097F]', text)): return True
    return False

def generate_voice(text):
    fname = f"response_{random.randint(1000,9999)}.mp3"
    try:
        lang = 'hi' if contains_hindi(text) else 'en'
        gTTS(text=text, lang=lang, tld='co.in').save(fname)
        return fname
    except: return None

def trigger_emergency_call(alert_type):
    if not twilio_client: return
    try:
        twilio_client.calls.create(
            twiml=f"<Response><Say loop='2'>Emergency Alert from Sandy. {alert_type} detected. Please check immediately.</Say></Response>",
            to=FAMILY_PHONE, from_=TWILIO_PHONE
        )
    except: pass

def get_weather_update():
    try:
        loc = httpx.get("https://ipinfo.io/json", verify=False).json()
        lat, lon = loc.get('loc', '28.61,77.20').split(',')
        city = loc.get('city', 'your city')
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        temp = httpx.get(url, verify=False).json()['current_weather']['temperature']
        return f"The current temperature in {city} is {temp} degrees Celsius."
    except: return "Weather unavailable."

# --- 3. USB CONTROL FUNCTIONS (Replaces Wi-Fi) ---

def send_command(cmd):
    """Sends text command to NodeMCU via USB"""
    if arduino and arduino.is_open:
        try:
            arduino.write(f"{cmd}\n".encode()) # Send 'on', 'off', etc.
            time.sleep(0.1)
            if arduino.in_waiting > 0:
                return arduino.readline().decode().strip()
            return "Command Sent"
        except: return "Connection Error"
    return "System Offline"

def control_house(command):
    cmd = command.lower()
    if "light" in cmd and "on" in cmd: 
        send_command("on")
        return "Turning Lights ON."
    elif "light" in cmd and "off" in cmd: 
        send_command("off")
        return "Turning Lights OFF."
    elif "door" in cmd and "open" in cmd: 
        send_command("door-open")
        return "Opening Door."
    elif "door" in cmd and "close" in cmd: 
        send_command("door-close")
        return "Closing Door."
    return ""

def get_home_telemetry():
    """Asks NodeMCU for status JSON via USB"""
    if arduino and arduino.is_open:
        try:
            # Clear old data
            while arduino.in_waiting > 0: arduino.read()
            
            # Request Status
            arduino.write(b"status\n")
            time.sleep(0.2)
            
            # Read Reply
            if arduino.in_waiting > 0:
                line = arduino.readline().decode().strip()
                if line.startswith("{"):
                    return json.loads(line)
        except: pass
    return None

# --- 4. THE BRAIN LOGIC ---

def process_logic(user_text, history):
    if not user_text: return "I am listening."

    # 1. SECURITY CONTROLS
    if "security" in user_text or "suraksha" in user_text:
        if "off" in user_text or "stop" in user_text:
            security_system.stop_camera()
            return "Security Deactivated."
        elif "on" in user_text or "start" in user_text:
            threading.Thread(target=security_system.start_camera_loop).start()
            return "Security Active."

    # 2. HOUSE CONTROL (Via USB)
    res = control_house(user_text)
    if res: return res

    # 3. EMERGENCY
    if "pain" in user_text or "chest" in user_text or "dizzy" in user_text:
        trigger_emergency_call("Medical Emergency")
        return "Calling family immediately."

    # 4. STATUS REPORT
    if "status" in user_text:
        d = get_home_telemetry()
        if d: return f"Lights: {d.get('hall')}. Door: {d.get('door')}. Gas: {d.get('gas')}."
        else: return "System Offline."

    # 5. GENERAL FEATURES (Weather, Time, Chat)
    if "weather" in user_text: return get_weather_update()
    if "time" in user_text: return datetime.now().strftime("The time is %I:%M %p.")
    
    if "play" in user_text:
        song = user_text.replace("play", "").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={song}")
        return f"Playing {song}."

    # 6. AI CONVERSATION
    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role":"system", "content":"You are Sandy. Keep your answer short and concise. Be polite"}] + history + [{"role":"user", "content":user_text}],
            max_tokens=100
        )
        return completion.choices[0].message.content
    except: return "No Internet."

# Export dummy variable so voice_mode doesn't crash
HOUSE_IP = "USB_MODE"