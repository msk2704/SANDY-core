import customtkinter as ctk
import threading
import speech_recognition as sr
import os
import math
import time
import tempfile
import backend  # Connects to your USB Brain
import pygame   # Replaces playsound to fix file locking

# --- 1. THEME & AUDIO SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")
pygame.mixer.init()

class VoiceOrbApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- STATE FLAGS ---
        self.danger_mode = False 
        self.current_state = "idle" 
        self.is_animating = True
        self.history = []

        # A. Window Setup
        self.title("S.A.N.D.Y. Command Interface")
        self.geometry("950x600") 
        self.configure(fg_color="#0f172a") # Deep Slate BG
        self.resizable(False, False)

        # --- LEFT SIDE: THE ORB ---
        self.orb_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.orb_frame.pack(side="left", fill="both", expand=True, padx=20)

        self.canvas_size = 350
        self.canvas = ctk.CTkCanvas(self.orb_frame, width=self.canvas_size, height=self.canvas_size, 
                                    bg="#0f172a", highlightthickness=0)
        self.canvas.pack(pady=(40, 20))
        
        self.center = self.canvas_size // 2
        self.radius = 80
        
        # Layered Orb for "Glow" effect
        self.orb_glow = self.canvas.create_oval(
            self.center - self.radius - 10, self.center - self.radius - 10,
            self.center + self.radius + 10, self.center + self.radius + 10,
            fill="#3b0764", outline="" 
        )
        self.orb = self.canvas.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            fill="#a855f7", outline="" 
        )

        self.status_label = ctk.CTkLabel(self.orb_frame, text="SYSTEM ONLINE", font=("Impact", 24), text_color="#64748b")
        self.status_label.pack()

        self.user_label = ctk.CTkLabel(self.orb_frame, text="Calibrating...", font=("Arial", 18, "italic"), text_color="white", wraplength=400)
        self.user_label.pack(pady=15)
        
        self.ai_label = ctk.CTkLabel(self.orb_frame, text="", font=("Arial", 16), text_color="#22d3ee", wraplength=400)
        self.ai_label.pack(pady=10)

        # --- RIGHT SIDE: DASHBOARD ---
        self.dash_frame = ctk.CTkFrame(self, fg_color="#1e293b", width=300, corner_radius=15, border_width=2, border_color="#38bdf8")
        self.dash_frame.pack(side="right", fill="y", padx=30, pady=30)
        self.dash_frame.pack_propagate(False)

        self.dash_title = ctk.CTkLabel(self.dash_frame, text="HOME STATUS", font=("Arial", 20, "bold"), text_color="white")
        self.dash_title.pack(pady=(20, 30))
        
        self.lbl_gas = ctk.CTkLabel(self.dash_frame, text="Air Quality: --", font=("Consolas", 18), text_color="#38bdf8")
        self.lbl_gas.pack(pady=10)
        
        ctk.CTkFrame(self.dash_frame, height=2, fg_color="#334155").pack(fill="x", padx=20, pady=20) 

        self.lbl_hall = ctk.CTkLabel(self.dash_frame, text="Hall Light: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_hall.pack(pady=5)
        
        self.lbl_bed = ctk.CTkLabel(self.dash_frame, text="Bedroom: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_bed.pack(pady=5)
        
        ctk.CTkFrame(self.dash_frame, height=2, fg_color="#334155").pack(fill="x", padx=20, pady=20) 

        self.lbl_door = ctk.CTkLabel(self.dash_frame, text="Front Door: LOCKED", font=("Consolas", 16, "bold"), text_color="#38bdf8")
        self.lbl_door.pack(pady=5)

        # --- START THREADS ---
        threading.Thread(target=self.pulse_animation, daemon=True).start()
        threading.Thread(target=self.auto_listen_loop, daemon=True).start()
        threading.Thread(target=self.update_dashboard_loop, daemon=True).start()

    # --- THREAD-SAFE UI UPDATERS ---
    def update_ui_state(self, state, status_text, user_text=None, ai_text=None):
        self.current_state = state
        if not self.danger_mode:
            self.status_label.configure(text=status_text)
        if user_text is not None:
            self.user_label.configure(text=f'"{user_text}"')
        if ai_text is not None:
            self.ai_label.configure(text=ai_text)

    def trigger_danger_ui(self, is_danger, gas_val):
        self.danger_mode = is_danger
        if is_danger:
            self.configure(fg_color="#450a0a")          
            self.canvas.configure(bg="#450a0a")         
            self.dash_frame.configure(fg_color="#7f1d1d", border_color="#ef4444")
            self.status_label.configure(text="⚠️ GAS LEAK DETECTED ⚠️", text_color="#ef4444")
            self.dash_title.configure(text="!! EMERGENCY !!", text_color="#ef4444")
            self.lbl_gas.configure(text=f"Air: {gas_val} (DANGER)", text_color="#ef4444")
            self.lbl_door.configure(text_color="#ef4444")
            self.ai_label.configure(text_color="#fecaca")
        else:
            self.configure(fg_color="#0f172a")          
            self.canvas.configure(bg="#0f172a")         
            self.dash_frame.configure(fg_color="#1e293b", border_color="#38bdf8")
            self.status_label.configure(text="SYSTEM ONLINE", text_color="#64748b")
            self.dash_title.configure(text="HOME STATUS", text_color="white")
            self.lbl_gas.configure(text=f"Air: {gas_val} (Safe)", text_color="#38bdf8")
            self.ai_label.configure(text_color="#38bdf8")

    def update_dashboard_labels(self, hall, bed, door):
        self.lbl_hall.configure(text=f"Hall Light: {hall}")
        self.lbl_bed.configure(text=f"Bedroom: {bed}")
        self.lbl_door.configure(text=f"Front Door: {door}")
        if door == "OPEN" and not self.danger_mode:
            self.lbl_door.configure(text_color="#ef4444")
        elif not self.danger_mode:
            self.lbl_door.configure(text_color="#38bdf8")

    # --- ANIMATION LOGIC ---
    def pulse_animation(self):
        step = 0
        while self.is_animating:
            try:
                pulse = math.sin(step) * 10 
                current_radius = self.radius + pulse
                
                if self.danger_mode:
                    color, glow, speed = "#ef4444", "#7f1d1d", 0.15      
                elif self.current_state == "listening":
                    color, glow, speed = "#a855f7", "#581c87", 0.05
                elif self.current_state == "thinking":
                    color, glow, speed = "#d946ef", "#86198f", 0.1
                elif self.current_state == "speaking":
                    color, glow, speed = "#22d3ee", "#0891b2", 0.08
                else:
                    color, glow, speed = "#64748b", "#334155", 0.05
                    
                # Schedule Canvas Updates on Main Thread
                self.after(0, self.canvas.coords, self.orb, 
                           self.center - current_radius, self.center - current_radius,
                           self.center + current_radius, self.center + current_radius)
                self.after(0, self.canvas.itemconfig, self.orb, fill=color)
                
                self.after(0, self.canvas.coords, self.orb_glow, 
                           self.center - current_radius - 12, self.center - current_radius - 12,
                           self.center + current_radius + 12, self.center + current_radius + 12)
                self.after(0, self.canvas.itemconfig, self.orb_glow, fill=glow)
                
                step += speed
                time.sleep(0.02)
            except Exception as e:
                print(f"Animation Error: {e}")
                time.sleep(1)

    # --- DASHBOARD LOOP ---
    def update_dashboard_loop(self):
        while True:
            try:
                data = backend.get_home_telemetry()
                if data:
                    self.after(0, self.update_dashboard_labels, data.get('hall', '--'), data.get('bedroom', '--'), data.get('door', '--'))
                    
                    gas_val = int(data.get('gas', 0))
                    if gas_val > 600 and not self.danger_mode:
                        self.after(0, self.trigger_danger_ui, True, gas_val)
                    elif gas_val <= 600 and self.danger_mode:
                        self.after(0, self.trigger_danger_ui, False, gas_val)
            except Exception as e:
                print(f"Dash Error: {e}")
            time.sleep(1)

    # --- DYNAMIC VOICE LISTENER ---
    def auto_listen_loop(self):
        r = sr.Recognizer()
        r.energy_threshold = 400
        r.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            print("Calibrating background noise...")
            r.adjust_for_ambient_noise(source, duration=1)
            print("Microphone Active.")
            self.after(0, self.update_ui_state, "idle", "READY", "Awaiting Command...")

            while True:
                try:
                    self.after(0, self.update_ui_state, "listening", "LISTENING...")
                    
                    # Dynamic listening: Stops recording immediately when the user stops talking
                    audio = r.listen(source, timeout=None, phrase_time_limit=10)
                    
                    self.after(0, self.update_ui_state, "thinking", "PROCESSING...")

                    # Safely handle the audio file without locking disk resources
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio.get_wav_data())
                        temp_path = f.name
                    
                    user_text = backend.transcribe_audio(temp_path)
                    os.remove(temp_path) # Clean up immediately

                    if not user_text: 
                        continue

                    print(f"User: {user_text}")
                    self.after(0, self.update_ui_state, "thinking", "PROCESSING...", user_text)
                    
                    response_text = backend.process_logic(user_text, self.history)
                    self.history.append({"role": "user", "content": user_text})
                    self.history.append({"role": "assistant", "content": response_text})
                    
                    self.after(0, self.update_ui_state, "speaking", "SPEAKING...", user_text, response_text)
                    
                    audio_file = backend.generate_voice(response_text)
                    if audio_file:
                        # Pygame allows explicit unloading of the file so OS can delete it
                        pygame.mixer.music.load(audio_file)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                        pygame.mixer.music.unload() 
                        os.remove(audio_file)
                
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    print(f"Voice Loop Error: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    app = VoiceOrbApp()
    app.mainloop()
