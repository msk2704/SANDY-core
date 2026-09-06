import os
import urllib.parse
import serial.tools.list_ports
from dotenv import load_dotenv
import speech_recognition as sr
from groq import Groq
from gtts import gTTS
import httpx
import random
import re
from datetime import datetime
import webbrowser
import threading
import serial
import time
import json
from twilio.rest import Client
import security_system

# --- 1. CONFIGURATION ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROK_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"

# --- GLOBAL FLAGS ---
security_active = False

# --- USB CONNECTION SETUP (AUTO-DETECT) ---
def find_microcontroller_port():
    ports = serial.tools.list_ports.comports()
    for port, desc, hwid in sorted(ports):
        if "USB" in desc or "CH340" in desc or "Arduino" in desc or "Serial" in desc:
            return port
    return 'COM5'  # Fallback port

SERIAL_PORT = find_microcontroller_port()
BAUD_RATE = 115200

try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"✅ USB Connection Established on {SERIAL_PORT}")
except serial.SerialException as e:
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

# --- INITIALIZATION ---
try:
    groq_client = Groq(api_key=GROQ_API_KEY)  # Uses default secure client
except Exception as e:
    print(f"❌ Groq Initialization Failed: {e}")
    groq_client = None

try:
    twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
except Exception as e:
    print(f"❌ Twilio Initialization Failed: {e}")
    twilio_client = None

# --- 2. SMART FUNCTIONS ---

def transcribe_audio(audio_filepath):
    if not audio_filepath: return ""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(audio_filepath) as source:
            return r.recognize_google(r.record(source), language='en-IN').lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"Speech API Error: {e}")
        return ""

def contains_hindi(text):
    return bool(re.search(r'[\u0900-\u097F]', text))

def generate_voice(text):
    fname = f"response_{random.randint(1000,9999)}.mp3"
    try:
        lang = 'hi' if contains_hindi(text) else 'en'
        gTTS(text=text, lang=lang, tld='co.in').save(fname)
        return fname
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

def trigger_emergency_call(alert_type):
    if not twilio_client:
        print("⚠️ Emergency Call Failed: Twilio client not initialized.")
        return
    try:
        twilio_client.calls.create(
            twiml=f"<Response><Say loop='2'>Emergency Alert from Sandy. {alert_type} detected. Please check immediately.</Say></Response>",
            to=FAMILY_PHONE, from_=TWILIO_PHONE
        )
        print("✅ Emergency Call Initiated.")
    except Exception as e:
        print(f"⚠️ Twilio API Call Error: {e}")

def get_weather_update():
    try:
        loc = httpx.get("https://ipinfo.io/json").json()
        lat, lon = loc.get('loc', '28.61,77.20').split(',')
        city = loc.get('city', 'your city')
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        temp = httpx.get(url).json()['current_weather']['temperature']
        return f"The current temperature in {city} is {temp} degrees Celsius."
    except httpx.RequestError as e:
        print(f"Weather Network Error: {e}")
        return "Weather unavailable due to network error."
    except KeyError:
        return "Weather data unavailable."

# --- 3. USB CONTROL FUNCTIONS (Replaces Wi-Fi) ---

def send_command(cmd):
    if arduino and arduino.is_open:
        try:
            arduino.write(f"{cmd}\n".encode())
            time.sleep(0.1)
            if arduino.in_waiting > 0:
                return arduino.readline().decode().strip()
            return "Command Sent"
        except serial.SerialException as e:
            print(f"Serial Write Error: {e}")
            return "Connection Error"
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
    if arduino and arduino.is_open:
        try:
            while arduino.in_waiting > 0: 
                arduino.read()
            arduino.write(b"status\n")
            time.sleep(0.2)
            if arduino.in_waiting > 0:
                line = arduino.readline().decode().strip()
                if line.startswith("{"):
                    return json.loads(line)
        except (serial.SerialException, json.JSONDecodeError) as e:
            print(f"Telemetry Read Error: {e}")
    return None

# --- 4. THE BRAIN LOGIC ---

def process_logic(user_text, history):
    global security_active
    
    if not user_text: return "I am listening."

    # 1. SECURITY CONTROLS
    if "security" in user_text or "suraksha" in user_text:
        if "off" in user_text or "stop" in user_text:
            if security_active:
                security_system.stop_camera()
                security_active = False
                return "Security Deactivated."
            return "Security is already off."
        elif "on" in user_text or "start" in user_text:
            if not security_active:
                threading.Thread(target=security_system.start_camera_loop, daemon=True).start()
                security_active = True
                return "Security Active."
            return "Security is already active."

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
        safe_song_query = urllib.parse.quote(song)
        webbrowser.open(f"https://www.youtube.com/results?search_query={safe_song_query}")
        return f"Playing {song}."

    # 6. AI CONVERSATION
    try:
        if not groq_client: return "AI core offline."
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role":"system", "content":"You are Sandy. Keep your answer short and concise. Be polite"}] + history + [{"role":"user", "content":user_text}],
            max_tokens=100
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"API Request Error: {e}")
        return "I am having trouble connecting to the network."

# Export dummy variable so voice_mode doesn't crash
HOUSE_IP = "USB_MODE"
