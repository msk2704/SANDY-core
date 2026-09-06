import customtkinter as ctk
import threading
import speech_recognition as sr
import pygame  # Replaces playsound for safe file handling
import os
import math
import time
import backend

# Initialize pygame mixer for safe audio handling
pygame.mixer.init()

# --- 1. THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class VoiceOrbApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- STATE FLAGS ---
        self.danger_mode = False 
        self.current_state = "idle" # idle, listening, thinking, speaking
        self.is_animating = True

        # A. Window Setup
        self.title("S.A.N.D.Y. Command Interface (USB MODE)")
        self.geometry("1000x650") 
        self.configure(fg_color="#0b0f19") # Darker, modern background
        self.resizable(False, False)

        # --- LEFT SIDE: THE ORB ---
        self.orb_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.orb_frame.pack(side="left", fill="both", expand=True, padx=20)

        # Canvas for the Orb
        self.canvas_size = 350
        self.canvas = ctk.CTkCanvas(self.orb_frame, width=self.canvas_size, height=self.canvas_size, 
                                    bg="#0b0f19", highlightthickness=0)
        self.canvas.pack(pady=(40, 10))
        
        self.center = self.canvas_size // 2
        self.radius = 85
        
        # Create the circle object
        self.orb = self.canvas.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            fill="#a855f7", outline="" 
        )

        self.status_label = ctk.CTkLabel(self.orb_frame, text="SYSTEM ONLINE", font=("Arial Black", 22), text_color="#64748b")
        self.status_label.pack(pady=(0, 5))

        self.user_label = ctk.CTkLabel(self.orb_frame, text="Awaiting command...", font=("Arial", 18, "italic"), text_color="white", wraplength=450)
        self.user_label.pack(pady=10)
        
        self.ai_label = ctk.CTkLabel(self.orb_frame, text="", font=("Arial", 18, "bold"), text_color="#38bdf8", wraplength=450)
        self.ai_label.pack(pady=10)

        # --- RIGHT SIDE: DASHBOARD ---
        self.dash_frame = ctk.CTkFrame(self, fg_color="#1e293b", width=320, corner_radius=20, border_width=2, border_color="#38bdf8")
        self.dash_frame.pack(side="right", fill="y", padx=30, pady=30)
        self.dash_frame.pack_propagate(False)

        # Dashboard Title
        self.dash_title = ctk.CTkLabel(self.dash_frame, text="HOME STATUS", font=("Arial Black", 20), text_color="white")
        self.dash_title.pack(pady=(25, 20))
        
        # Air Quality Card
        self.card_gas = ctk.CTkFrame(self.dash_frame, fg_color="#0f172a", corner_radius=10)
        self.card_gas.pack(fill="x", padx=20, pady=10)
        self.lbl_gas = ctk.CTkLabel(self.card_gas, text="Air Quality: --", font=("Consolas", 18, "bold"), text_color="#38bdf8")
        self.lbl_gas.pack(pady=15)

        # Rooms Card
        self.card_rooms = ctk.CTkFrame(self.dash_frame, fg_color="#0f172a", corner_radius=10)
        self.card_rooms.pack(fill="x", padx=20, pady=10)
        self.lbl_hall = ctk.CTkLabel(self.card_rooms, text="Hall Light: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_hall.pack(pady=(15, 5))
        self.lbl_bed = ctk.CTkLabel(self.card_rooms, text="Bedroom: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_bed.pack(pady=(5, 15))
        
        # Security Card
        self.card_door = ctk.CTkFrame(self.dash_frame, fg_color="#0f172a", corner_radius=10)
        self.card_door.pack(fill="x", padx=20, pady=10)
        self.lbl_door = ctk.CTkLabel(self.card_door, text="Front Door: LOCKED", font=("Consolas", 16, "bold"), text_color="#38bdf8")
        self.lbl_door.pack(pady=15)

        # --- THREADS ---
        threading.Thread(target=self.pulse_animation, daemon=True).start()
        threading.Thread(target=self.auto_listen_loop, daemon=True).start()
        threading.Thread(target=self.update_dashboard_loop, daemon=True).start()

    # --- THREAD-SAFE UI UPDATERS ---
    def set_state_ui(self, state, status_text, user_text=None, ai_text=None):
        """Safely updates main text labels from background threads."""
        self.current_state = state
        self.status_label.configure(text=status_text)
        if user_text is not None:
            self.user_label.configure(text=user_text)
        if ai_text is not None:
            self.ai_label.configure(text=ai_text)

    def update_orb_canvas(self, radius, color):
        """Safely redraws the canvas from the animation thread."""
        self.canvas.coords(self.orb, 
                           self.center - radius, self.center - radius,
                           self.center + radius, self.center + radius)
        self.canvas.itemconfig(self.orb, fill=color)

    def trigger_danger_ui(self, active, gas_val):
        """Safely handles the transition into and out of danger mode."""
        self.danger_mode = active
        if active:
            self.configure(fg_color="#270000")          
            self.canvas.configure(bg="#270000")         
            self.dash_frame.configure(fg_color="#3b0000", border_color="#ef4444")
            
            self.status_label.configure(text="⚠️ GAS LEAK ⚠️", text_color="#ef4444")
            self.dash_title.configure(text="!! EMERGENCY !!", text_color="#ef4444")
            self.lbl_gas.configure(text=f"Air: {gas_val} (DANGER)", text_color="#ef4444")
            self.ai_label.configure(text_color="#fca5a5")
        else:
            self.configure(fg_color="#0b0f19")          
            self.canvas.configure(bg="#0b0f19")         
            self.dash_frame.configure(fg_color="#1e293b", border_color="#38bdf8")
            
            if self.current_state == "idle":
                self.status_label.configure(text="SYSTEM ONLINE", text_color="#64748b")
            self.dash_title.configure(text="HOME STATUS", text_color="white")
            self.lbl_gas.configure(text=f"Air: {gas_val} (Safe)", text_color="#38bdf8")
            self.ai_label.configure(text_color="#38bdf8")

    def update_telemetry_ui(self, data):
        """Safely parses and updates the dashboard data."""
        gas_val = int(data.get('gas', 0))
        self.trigger_danger_ui(gas_val > 600, gas_val)

        self.lbl_hall.configure(text=f"Hall Light: {data.get('hall', '--')}")
        self.lbl_bed.configure(text=f"Bedroom: {data.get('bedroom', '--')}")

        door_status = data.get('door', '--')
        if door_status == "OPEN":
            self.lbl_door.configure(text=f"Front Door: {door_status}", text_color="#ef4444") 
        elif not self.danger_mode:
            self.lbl_door.configure(text=f"Front Door: {door_status}", text_color="#38bdf8")

    # --- BACKGROUND THREADS ---
    def pulse_animation(self):
        step = 0
        while self.is_animating:
            try:
                pulse = math.sin(step) * 10 
                current_radius = self.radius + pulse
                
                # Dynamic Speed & Color Logic
                if self.danger_mode:
                    color, speed = "#ef4444", 0.15 # RED
                elif self.current_state == "listening":
                    color, speed = "#a855f7", 0.05 # PURPLE
                elif self.current_state == "thinking":
                    color, speed = "#d946ef", 0.10 # PINK
                elif self.current_state == "speaking":
                    color, speed = "#38bdf8", 0.08 # CYAN
                else:
                    color, speed = "#475569", 0.03 # IDLE (Slate)
                    
                # Offload UI update to the main Tkinter thread
                self.after(0, self.update_orb_canvas, current_radius, color)
                
                step += speed
                time.sleep(0.02)
            except Exception as e:
                print(f"Animation Error: {e}")
                time.sleep(1)

    def update_dashboard_loop(self):
        while True:
            try:
                data = backend.get_home_telemetry()
                if data:
                    self.after(0, self.update_telemetry_ui, data)
                else:
                    self.after(0, self.lbl_gas.configure, {"text": "STATUS: OFFLINE"})
            except Exception as e:
                print(f"Dashboard Update Error: {e}")
            time.sleep(1.5)

    def auto_listen_loop(self):
        # Replaces fixed 5-second disk recording with dynamic silence detection in memory
        r = sr.Recognizer()
        r.energy_threshold = 400 
        r.dynamic_energy_threshold = True
        history = []
        
        print("Microphone Initializing...")
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            print("Microphone Active.")
            
            while True:
                try:
                    self.after(0, self.set_state_ui, "idle", "LISTENING...", "Awaiting command...", "")
                    
                    try:
                        # Dynamically listens until the user stops speaking
                        audio = r.listen(source, timeout=1, phrase_time_limit=15)
                    except sr.WaitTimeoutError:
                        continue 
                        
                    self.after(0, self.set_state_ui, "thinking", "PROCESSING...", "Transcribing...", "")
                    
                    try:
                        user_text = r.recognize_google(audio, language='en-IN').lower()
                    except sr.UnknownValueError:
                        continue 
                    except sr.RequestError as e:
                        print(f"STT Network Error: {e}")
                        continue
                        
                    print(f"User: {user_text}")
                    self.after(0, self.set_state_ui, "thinking", "THINKING...", f'"{user_text}"', "Analyzing...")
                    
                    # Logic processing
                    response_text = backend.process_logic(user_text, history)
                    history.append({"role": "user", "content": user_text})
                    history.append({"role": "assistant", "content": response_text})
                    
                    self.after(0, self.set_state_ui, "speaking", "SPEAKING...", f'"{user_text}"', response_text)
                    
                    # Generate and play audio cleanly
                    audio_file = backend.generate_voice(response_text)
                    if audio_file:
                        try:
                            pygame.mixer.music.load(audio_file)
                            pygame.mixer.music.play()
                            while pygame.mixer.music.get_busy():
                                time.sleep(0.1)
                            
                            # Explicitly unload to release the file lock on Windows
                            pygame.mixer.music.unload() 
                            os.remove(audio_file)
                        except Exception as e:
                            print(f"Audio Playback/Cleanup Error: {e}")
                            
                except Exception as e:
                    print(f"Mic Loop Error: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    app = VoiceOrbApp()
    app.mainloop()
