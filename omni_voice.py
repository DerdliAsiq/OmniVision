import os
import sys
import difflib

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"

import io
import time
import threading
import subprocess
import logging
import speech_recognition as sr
from config import SystemState

try:
    from faster_whisper import WhisperModel, download_model
except ImportError:
    WhisperModel = None
    download_model = None

logger = logging.getLogger("OmniVoice")

class OmniVoice:
    def __init__(self):
        self.is_running = False
        self.model = None
        
        if WhisperModel is None:
            logger.error("[X] faster-whisper paketi eksik! Ses motoru başlatılamadı.")
            return
            
        try:
            model_dir = "whisper_model_local"
            
            if not os.path.exists(model_dir):
                print("\n" + "="*60)
                print("[!] DİKKAT: J.A.R.V.I.S. Beyin Dosyaları Eksik!")
                print(f"[*] Faster-Whisper 'Tiny' modeli '{model_dir}' klasörüne indiriliyor...")
                download_model("tiny", output_dir=model_dir)
                print("[+] İndirme tamamlandı! Artık sistem %100 ÇEVRİMDIŞI çalışacak.")
                print("="*60 + "\n")

            logger.info(f"[*] J.A.R.V.I.S. Kulakları Lokal Klasörden Yükleniyor... (CPU MODU)")
            # Taktik 1: device="cpu" ve compute_type="int8" yapılarak VRAM tamamen boşaltıldı!
            self.model = WhisperModel(model_dir, device="cpu", compute_type="int8")
            
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True 
            self.is_speaking = False 
            
            logger.info("[+] Ses Karargahı (Voice C2) Hazır. (Kısayol: 'V' tuşu ile aktif edin)")
            
        except Exception as e:
            logger.error(f"[X] Ses motoru başlatma hatası: {e}")

    def play_feedback(self, audio_file):
        file_path = os.path.join("c2_audio", audio_file)
        if os.path.exists(file_path):
            self.is_speaking = True 
            process = subprocess.Popen(["mpg123", "-q", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            def wait_for_audio():
                process.wait()
                time.sleep(0.5) 
                self.is_speaking = False
                
            threading.Thread(target=wait_for_audio, daemon=True).start()
        else:
            logger.warning(f"[!] Ses mühimmatı eksik: {file_path}")

    def start(self):
        if self.model is None:
            return
        self.is_running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _listen_loop(self):
        while self.is_running:
            if not SystemState.VOICE_COMMANDS_ACTIVE:
                time.sleep(0.5)
                continue
                
            try:
                with sr.Microphone(sample_rate=16000) as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    print("\n[🎙️] MİKROFON AKTİF: Dinleniyor... (Stealth Mod Kapalı)")
                    
                    while self.is_running and SystemState.VOICE_COMMANDS_ACTIVE:
                        if self.is_speaking:
                            time.sleep(0.1)
                            continue
                            
                        try:
                            audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                            if not self.is_speaking:
                                self._process_audio(audio)
                        except sr.WaitTimeoutError:
                            continue
                        except Exception:
                            time.sleep(0.5)
            except Exception as e:
                logger.error(f"[X] Mikrofon donanımına erişilemedi: {e}")
                time.sleep(1)
            
            if self.is_running:
                print("\n[🔇] MİKROFON KAPALI: Sistem sağırlaştırıldı (Stealth Mod Aktif).")

    def _fuzzy_match_intent(self, text):
        wake_words = ["alfa", "alpha", "halfa", "arfa", "aysa", "alpa", "alza", "asa", "aza", "alf"]
        
        is_awake = False
        words = text.replace(".", "").replace(",", "").replace("?", "").split()
        
        for w in wake_words:
            if w in text or difflib.get_close_matches(w, words, n=1, cutoff=0.8):
                is_awake = True
                break
                
        if not is_awake:
            return None
            
        clean_words = [word for word in words if word not in wake_words]
        clean_text = " ".join(clean_words)
        
        if len(clean_words) == 0 or len(clean_text) < 3:
            return "LISTENING"

        def match_any(targets, cutoff=0.8):
            for t in targets:
                if t in clean_text: return True
                if difflib.get_close_matches(t, clean_words, n=1, cutoff=cutoff): return True
            return False
            
        has_alarm = match_any(["alarm", "alarım", "alarmi", "alarmı", "aktir"])
        has_panel = match_any(["panel", "paneli", "planeli", "ekran", "arayüz", "phaneli"])
        
        is_active = match_any(["aktif", "aç", "açı", "başlat"])
        is_inactive = match_any(["kapat", "gizle", "gizli", "devre", "durdur"])
        
        if has_alarm and is_active: return "ALARM_ON"
        if has_alarm and is_inactive: return "ALARM_OFF"
        if has_panel and is_inactive: return "PANEL_OFF"
        if has_panel and is_active: return "PANEL_ON"
        
        if not has_alarm and not has_panel and not is_active and not is_inactive:
            return "LISTENING"
        
        return "UNKNOWN"

    def _process_audio(self, audio):
        try:
            wav_data = audio.get_wav_data()
            audio_stream = io.BytesIO(wav_data)
            
            segments, info = self.model.transcribe(
                audio_stream, 
                beam_size=1, 
                condition_on_previous_text=False,
                language="tr",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                initial_prompt="Alfa paneli aç. Alfa paneli gizle. Alfa alarm aktif. Alfa alarmı kapat."
            )
            
            text_parts = []
            for segment in segments:
                try:
                    text_parts.append(segment.text)
                except Exception:
                    continue
                    
            raw_text = " ".join(text_parts).strip().lower()
            
            if not raw_text or "komut" in raw_text or "anlaşılamadı" in raw_text:
                return
            
            print(f"\n[🎧 RÖNTGEN - SİSTEM BUNU DUYDU] -> {raw_text}")
            
            intent = self._fuzzy_match_intent(raw_text)
            
            if intent:
                print(f"[🗣️ ALFA UYANDI: NİYET TESPİT EDİLDİ -> {intent}]")
                
                if intent == "ALARM_ON":
                    SystemState.ALARM_MODE = True
                    self.play_feedback("alarm_on.mp3")
                elif intent == "ALARM_OFF":
                    SystemState.ALARM_MODE = False
                    self.play_feedback("alarm_off.mp3")
                elif intent == "PANEL_OFF":
                    SystemState.SHOW_DASHBOARD = False
                    self.play_feedback("hud_off.mp3")
                elif intent == "PANEL_ON":
                    SystemState.SHOW_DASHBOARD = True
                    self.play_feedback("hud_on.mp3")
                elif intent == "LISTENING":
                    self.play_feedback("listening.mp3")
                elif intent == "UNKNOWN":
                    self.play_feedback("error.mp3")

        except Exception as e:
            pass