import customtkinter as ctk
import threading
import speech_recognition as sr
import playsound
import os
import math
import time
import backend  # <--- Connects to your USB Brain
import sounddevice as sd
import soundfile as sf
import numpy as np

# --- 1. THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class VoiceOrbApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- STATE FLAGS ---
        self.danger_mode = False 
        self.current_state = "idle" # idle, listening, thinking, speaking

        # A. Window Setup
        self.title("S.A.N.D.Y. Command Interface (USB MODE)")
        self.geometry("950x600") 
        self.configure(fg_color="#0f0c29") # Deep Space Blue BG
        self.resizable(False, False)

        # --- LEFT SIDE: THE ORB ---
        self.orb_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.orb_frame.pack(side="left", fill="both", expand=True, padx=20)

        # Canvas for the Orb
        self.canvas_size = 350
        self.canvas = ctk.CTkCanvas(self.orb_frame, width=self.canvas_size, height=self.canvas_size, 
                                    bg="#0f0c29", highlightthickness=0)
        self.canvas.pack(pady=(40, 20))
        
        self.center = self.canvas_size // 2
        self.radius = 80
        # Create the circle object
        self.orb = self.canvas.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            fill="#a855f7", outline="" 
        )

        self.status_label = ctk.CTkLabel(self.orb_frame, text="SYSTEM ONLINE", font=("Impact", 24), text_color="gray")
        self.status_label.pack()

        self.user_label = ctk.CTkLabel(self.orb_frame, text="Listening...", font=("Arial", 18, "italic"), text_color="white", wraplength=400)
        self.user_label.pack(pady=15)
        
        self.ai_label = ctk.CTkLabel(self.orb_frame, text="", font=("Arial", 16), text_color="#22d3ee", wraplength=400)
        self.ai_label.pack(pady=10)

        # --- RIGHT SIDE: DASHBOARD ---
        self.dash_frame = ctk.CTkFrame(self, fg_color="#161b33", width=300, corner_radius=15, border_width=2, border_color="#22d3ee")
        self.dash_frame.pack(side="right", fill="y", padx=30, pady=30)
        self.dash_frame.pack_propagate(False)

        # Dashboard Title
        self.dash_title = ctk.CTkLabel(self.dash_frame, text="HOME STATUS", font=("Arial", 20, "bold"), text_color="white")
        self.dash_title.pack(pady=(20, 30))
        
        # Labels (Water Removed)
        self.lbl_gas = ctk.CTkLabel(self.dash_frame, text="Air Quality: --", font=("Consolas", 18), text_color="#22d3ee")
        self.lbl_gas.pack(pady=10)
        
        ctk.CTkFrame(self.dash_frame, height=2, fg_color="gray").pack(fill="x", padx=20, pady=20) 

        # Room Status
        self.lbl_hall = ctk.CTkLabel(self.dash_frame, text="Hall Light: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_hall.pack(pady=5)
        
        self.lbl_bed = ctk.CTkLabel(self.dash_frame, text="Bedroom: OFF", font=("Consolas", 16), text_color="white")
        self.lbl_bed.pack(pady=5)
        
        ctk.CTkFrame(self.dash_frame, height=2, fg_color="gray").pack(fill="x", padx=20, pady=20) 

        self.lbl_door = ctk.CTkLabel(self.dash_frame, text="Front Door: LOCKED", font=("Consolas", 16, "bold"), text_color="#22d3ee")
        self.lbl_door.pack(pady=5)

        # --- THREADS ---
        self.is_animating = True

        # 1. Animation Thread
        threading.Thread(target=self.pulse_animation, daemon=True).start()
        # 2. Voice Listener Thread
        threading.Thread(target=self.auto_listen_loop, daemon=True).start()
        # 3. Dashboard Update Thread
        threading.Thread(target=self.update_dashboard_loop, daemon=True).start()

    # --- ANIMATION LOGIC ---
    def pulse_animation(self):
        step = 0
        while self.is_animating:
            try:
                # Breathing Math
                pulse = math.sin(step) * 10 
                current_radius = self.radius + pulse
                
                # Color Logic based on State
                if self.danger_mode:
                    color = "#ff0000" # RED (Emergency)
                    speed = 0.15      
                elif self.current_state == "listening":
                    color = "#a855f7" # PURPLE (Listening)
                    speed = 0.05
                elif self.current_state == "thinking":
                    color = "#d946ef" # PINK (Thinking)
                    speed = 0.1
                elif self.current_state == "speaking":
                    color = "#22d3ee" # CYAN (Speaking)
                    speed = 0.08
                else:
                    color = "gray"    # IDLE
                    speed = 0.05
                    
                # Update Orb on Screen
                self.canvas.coords(self.orb, 
                                 self.center - current_radius, self.center - current_radius,
                                 self.center + current_radius, self.center + current_radius)
                self.canvas.itemconfig(self.orb, fill=color)
                
                step += speed
                time.sleep(0.02)
            except Exception:
                pass 

    # --- DASHBOARD LOOP (UPDATED FOR USB) ---
    def update_dashboard_loop(self):
        while True:
            try:
                # DIRECT CALL TO BACKEND (No 'requests.get')
                data = backend.get_home_telemetry()
                
                if data:
                    # Update Lights
                    self.lbl_hall.configure(text=f"Hall Light: {data.get('hall', '--')}")
                    self.lbl_bed.configure(text=f"Bedroom: {data.get('bedroom', '--')}")
                    self.lbl_door.configure(text=f"Front Door: {data.get('door', '--')}")

                    # GAS CHECK
                    gas_val = int(data.get('gas', 0))
                    
                    if gas_val > 600:
                        # !!! DANGER MODE !!!
                        if not self.danger_mode: 
                            self.danger_mode = True
                            
                            # Turn Interface RED
                            self.configure(fg_color="#1a0000")          
                            self.canvas.configure(bg="#1a0000")         
                            self.dash_frame.configure(fg_color="#2b0505", border_color="#ff0000")
                            
                            self.status_label.configure(text="⚠️ GAS LEAK DETECTED ⚠️", text_color="#ff0000")
                            self.dash_title.configure(text="!! EMERGENCY !!", text_color="#ff0000")
                            self.lbl_gas.configure(text_color="#ff0000")
                            self.lbl_door.configure(text_color="#ff0000")
                            self.ai_label.configure(text_color="#ffcccc")

                        self.lbl_gas.configure(text=f"Air: {gas_val} (DANGER)")
                        
                    else:
                        # SAFE MODE
                        if self.danger_mode: 
                            self.danger_mode = False
                            
                            # Restore Blue Theme
                            self.configure(fg_color="#0f0c29")          
                            self.canvas.configure(bg="#0f0c29")         
                            self.dash_frame.configure(fg_color="#161b33", border_color="#22d3ee")
                            
                            self.status_label.configure(text="SYSTEM ONLINE", text_color="gray")
                            self.dash_title.configure(text="HOME STATUS", text_color="white")
                            self.lbl_gas.configure(text_color="#22d3ee")
                            self.lbl_door.configure(text_color="#22d3ee")
                            self.ai_label.configure(text_color="#22d3ee")

                        self.lbl_gas.configure(text=f"Air: {gas_val} (Safe)")

                    # DOOR COLOR
                    if data.get('door') == "OPEN":
                        self.lbl_door.configure(text_color="#ef4444") 
                    elif not self.danger_mode:
                        self.lbl_door.configure(text_color="#22d3ee")
                else:
                    self.lbl_gas.configure(text="STATUS: CONNECTING...")

            except Exception as e:
                # print(f"Dash Error: {e}") # Optional: Uncomment to debug
                pass
            
            time.sleep(1)

    # --- VOICE LISTENER LOOP ---
    def auto_listen_loop(self):
        fs = 44100
        print("Microphone Active.")
        history = []
        
        while True:
            try:
                # 1. LISTEN
                self.current_state = "listening"
                if not self.danger_mode:
                    self.status_label.configure(text="LISTENING...")
                
                myrecording = sd.rec(int(5 * fs), samplerate=fs, channels=1)
                sd.wait()
                
                # Silence Check
                if np.linalg.norm(myrecording) * 10 < 20: continue 

                sf.write('temp_input.wav', myrecording, fs)
                
                # 2. THINK
                self.current_state = "thinking"
                if not self.danger_mode:
                    self.status_label.configure(text="PROCESSING...")

                try:
                    user_text = backend.transcribe_audio('temp_input.wav')
                    if not user_text: continue

                    print(f"User: {user_text}")
                    self.user_label.configure(text=f'"{user_text}"')
                    
                    response_text = backend.process_logic(user_text, history)
                    
                    history.append({"role": "user", "content": user_text})
                    history.append({"role": "assistant", "content": response_text})
                    
                    self.ai_label.configure(text=response_text)
                    
                    # 3. SPEAK
                    self.current_state = "speaking"
                    if not self.danger_mode:
                        self.status_label.configure(text="SPEAKING...")
                    
                    audio_file = backend.generate_voice(response_text)
                    if audio_file:
                        playsound.playsound(audio_file)
                        try: os.remove(audio_file)
                        except: pass
                    
                except Exception as e:
                    print(f"Logic Loop Error: {e}")
                
                try: os.remove('temp_input.wav')
                except: pass

            except Exception as e:
                print(f"Mic Loop Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    app = VoiceOrbApp()
    app.mainloop()