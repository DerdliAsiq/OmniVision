import os
import sys
import difflib
import io
import time
import threading
import logging
import speech_recognition as sr
from config import SystemState

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

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

        # Mikrofon girisi icin PyAudio sart (SpeechRecognition alternatifi yok).
        try:
            import pyaudio  # noqa: F401
            self.has_pyaudio = True
        except ImportError:
            self.has_pyaudio = False
            print("[X] PyAudio eksik! Mikrofon calismaz. Cozum: pip install PyAudio")
            logger.error("[X] PyAudio bulunamadi. Sesli komutlar devre disi.")
        
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except:
            pass
        
        if WhisperModel is None:
            logger.error("[X] faster-whisper paketi eksik! Ses motoru başlatılamadı.")
            return
            
        try:
            from pathlib import Path as _P
            try:
                from config import SystemState as _SS
                model_dir = str(_P(str(_SS.BASE_DIR)) / "whisper_model_local")
            except Exception:
                model_dir = "whisper_model_local"
            
            if not os.path.exists(model_dir):
                print("\n" + "="*60)
                print("[!] DİKKAT: J.A.R.V.I.S. Beyin Dosyaları Eksik!")
                print(f"[*] Faster-Whisper 'Tiny' modeli '{model_dir}' klasörüne indiriliyor...")
                download_model("tiny", output_dir=model_dir)
                print("[+] İndirme tamamlandı. Sistem ÇEVRİMDIŞI çalışacak.")
                print("="*60 + "\n")

            logger.info("[*] Ses Motoru Yükleniyor... (Ryzen CPU Çekirdeklerine Pinleniyor)")
            # [SIFIR HATA & VRAM İZOLASYONU] Whisper'ı GPU'dan uzak tutmak için CPU thread'leri sınırlandı.
            self.model = WhisperModel(model_dir, device="cpu", compute_type="int8", cpu_threads=4)
            
            self.recognizer = sr.Recognizer()
            # [WINDOWS WASAPI FIX] Sonsuz dinleme (timeout) bug'ını engellemek için statik eşik.
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = 400 
            self.is_speaking = False 
            
            logger.info("[+] Ses Karargahı (Voice C2) Hazır.")
            
        except Exception as e:
            logger.error(f"[X] Ses motoru başlatma hatası: {e}")

    def play_feedback(self, audio_file):
        file_path = os.path.join("c2_audio", audio_file)
        if os.path.exists(file_path):
            self.is_speaking = True 
            try:
                sound = pygame.mixer.Sound(file_path)
                sound.play()
                
                def wait_for_audio():
                    time.sleep(sound.get_length() + 0.2)
                    self.is_speaking = False
                    
                threading.Thread(target=wait_for_audio, daemon=True).start()
            except Exception as e:
                logger.error(f"Ses çalma hatası: {e}")
                self.is_speaking = False
        else:
            logger.warning(f"[!] Ses mühimmatı eksik: {file_path}")

    def is_ready(self):
        """Sesli komut motoru goreve hazir mi? (model + PyAudio + dinleme dongusu)"""
        return self.model is not None and self.has_pyaudio and self.is_running

    def start(self):
        if self.model is None:
            logger.error("[X] Whisper modeli yuklenemedi. Sesli komutlar devre disi.")
            return
        if not self.has_pyaudio:
            logger.error("[X] PyAudio eksik (pip install PyAudio). Sesli komutlar devre disi.")
            return
        self.is_running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.is_running = False

    def _listen_loop(self):
        fail_count = 0
        while self.is_running:
            if not SystemState.VOICE_COMMANDS_ACTIVE:
                time.sleep(0.5)
                continue

            try:
                # Mikrofonu dongu disinda TEK KEZ ac (her hatada yeniden acma).
                with sr.Microphone(sample_rate=16000) as source:
                    # Windows'ta ortam gürültüsüne adaptasyon süresini kısalttık
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    print("\n[🎙️] MİKROFON AKTİF (Stealth Mod Kapalı)")
                    fail_count = 0

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
                # Artan bekleme (backoff): log sismesini engeller, 5sn'de tavan yapar.
                fail_count += 1
                wait = min(1 + fail_count, 5)
                logger.error(f"[X] Mikrofon hatası: {e} ({wait}sn sonra tekrar denenecek)")
                time.sleep(wait)

    def _fuzzy_match_intent(self, text):
        # Uyandirma kelimesi token-eslesmeli: substring "asa" gibi parcalar tetiklemesin.
        wake_words = ["alfa", "alpha"]
        wake_aliases = {"halfa", "arfa", "alpa", "alza"}
        
        is_awake = False
        words = text.replace(".", "").replace(",", "").replace("?", "").split()

        for tok in words:
            if tok in wake_words:
                is_awake = True
                break
            if tok in wake_aliases or difflib.get_close_matches(tok, wake_words, n=1, cutoff=0.9):
                is_awake = True
                break
                
        if not is_awake: return None
            
        clean_words = [word for word in words if word not in wake_words]
        clean_text = " ".join(clean_words)
        
        if len(clean_words) == 0 or len(clean_text) < 3: return "LISTENING"

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
                initial_prompt="Alfa paneli aç. Alfa paneli gizle. Alfa alarm aktif."
            )
            
            raw_text = " ".join([segment.text for segment in segments]).strip().lower()
            
            if not raw_text or "komut" in raw_text or "anlaşılamadı" in raw_text: return
            
            print(f"\n[🎧 SİSTEM DUYDU] -> {raw_text}")
            intent = self._fuzzy_match_intent(raw_text)

            if not intent:
                print("[!] Uyandirma kelimesi ('alfa') algilanamadi. Ornek: 'alfa alarm aktif'")
            
            if intent:
                print(f"[🗣️ NİYET TESPİT EDİLDİ -> {intent}]")
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
            logger.error(f"Ses komut işleme hatası: {e}")