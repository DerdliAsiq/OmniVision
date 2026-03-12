import cv2
import psutil
import numpy as np
import time
import threading
import os
import logging
import subprocess
from config import SystemState

class TacticalUI:
    def __init__(self):
        # Genel arayüz fontu (Siberpunk görünüm için Simplex kalıyor)
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        # Tehdit uyarısı için Times New Roman tarzı ağır font (0 performans kaybı)
        self.alert_font = cv2.FONT_HERSHEY_COMPLEX 
        self.panel_width = 340 
        self.alarm_file = "alarm.mp3"
        
        if not os.path.exists(self.alarm_file):
            logging.warning(f"[{self.alarm_file}] bulunamadı! Lütfen dosyayı proje dizinine ekleyin.")

    def _play_alarm_sound(self):
        """Asenkron Akıllı Ses Kilidi (Smart Lock)"""
        if SystemState.IS_AUDIO_PLAYING:
            return
            
        SystemState.IS_AUDIO_PLAYING = True 
        
        if os.path.exists(self.alarm_file):
            try:
                subprocess.run(["mpg123", "-q", self.alarm_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                try:
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", self.alarm_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    print("\a", end="", flush=True) 
                    time.sleep(1) 
        else:
            print("\a", end="", flush=True)
            time.sleep(1)
            
        SystemState.IS_AUDIO_PLAYING = False 

    def draw_dashboard(self, frame, fps):
        h, w = frame.shape[:2]

        if SystemState.IS_THREAT_DETECTED and not SystemState.IS_AUDIO_PLAYING:
            threading.Thread(target=self._play_alarm_sound, daemon=True).start()

        # --- GÖRSEL ŞOK EFEKTİ (HUD KAPALI OLSA BİLE ÇİZİLİR) ---
        if SystemState.IS_THREAT_DETECTED:
            # Kan kırmızı dış çerçeve
            cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 255), 15)
            warn_text = "CRITICAL THREAT DETECTED"
            # Times New Roman benzeri ağır fontu kullanıyoruz
            ws = cv2.getTextSize(warn_text, self.alert_font, 1.2, 3)[0]
            wx = (w - ws[0]) // 2
            wy = 50
            # Kırmızı arka plan ve beyaz metin
            cv2.rectangle(frame, (wx - 10, wy - 35), (wx + ws[0] + 10, wy + 15), (0, 0, 255), -1)
            cv2.putText(frame, warn_text, (wx, wy), self.alert_font, 1.2, (255, 255, 255), 3)

        # --- ERKEN ÇIKIŞ ---
        # Eğer HUD (Yan Panel) gizlendiyse, arayüzü çizme ve doğrudan kamerayı geri yolla.
        # Üstteki blok sayesinde kırmızı uyarı yazısı ekranda kalmış olacak!
        if not SystemState.SHOW_DASHBOARD:
            return frame

        canvas = np.zeros((h, w + self.panel_width, 3), dtype=np.uint8)
        canvas[0:h, 0:w] = frame

        overlay = canvas.copy()
        cv2.rectangle(overlay, (w, 0), (w + self.panel_width, h), (12, 12, 12), -1) 
        cv2.rectangle(overlay, (0, h - 35), (w + self.panel_width, h), (18, 18, 18), -1) 
        cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)

        x_offset = w + 20

        cv2.putText(canvas, "[ OMNIVISION CORE ]", (x_offset, 35), self.font, 0.7, (0, 255, 255), 2)
        cv2.line(canvas, (x_offset, 50), (x_offset + self.panel_width - 40, 50), (80, 80, 80), 1)

        # 1. BÖLÜM: TEHDİT HEDEFLEME
        y = 85
        cv2.putText(canvas, "[ THREAT ACQUISITION ]", (x_offset, y), self.font, 0.55, (255, 200, 0), 2)
        y += 30
        
        target_str = ", ".join(SystemState.ACTIVE_TARGET_NAMES)
        if len(target_str) > 23:
            target_str = target_str[:20] + "..."
        if not target_str:
            target_str = "NONE"
            
        cv2.putText(canvas, f"TARGET : > {target_str} <", (x_offset, y), self.font, 0.45, (255, 255, 255), 1)

        y += 25
        alarm_color = (0, 255, 0) if SystemState.ALARM_MODE else (100, 100, 100)
        alarm_status = "ENGAGED" if SystemState.ALARM_MODE else "STANDBY"
        cv2.putText(canvas, f"RADAR  : [{alarm_status}]", (x_offset, y), self.font, 0.5, alarm_color, 2)

        # 2. BÖLÜM: SİSTEM MODÜLLERİ
        y += 60
        cv2.putText(canvas, "[ SYSTEM MODULES ]", (x_offset, y), self.font, 0.55, (255, 200, 0), 2)
        y += 30
        self._draw_status(canvas, "Tracking (T)", SystemState.TRACKING_ACTIVE, x_offset, y)
        y += 25
        self._draw_status(canvas, "LiDAR    (L)", SystemState.LIDAR_ACTIVE, x_offset, y)
        y += 25
        self._draw_status(canvas, "Horizon  (H)", SystemState.HORIZON_SCAN_ACTIVE, x_offset, y)

        # 3. BÖLÜM: PERFORMANS 
        y += 60
        if SystemState.SHOW_PERFORMANCE:
            cv2.putText(canvas, "[ METRICS ]", (x_offset, y), self.font, 0.55, (255, 200, 0), 2)
            y += 30
            cv2.putText(canvas, f"FPS : {int(fps)}", (x_offset, y), self.font, 0.5, (0, 255, 255), 1)
            y += 25
            cv2.putText(canvas, f"CPU : %{psutil.cpu_percent()}", (x_offset, y), self.font, 0.5, (0, 255, 0), 1)
            y += 25
            cv2.putText(canvas, f"RAM : %{psutil.virtual_memory().percent}", (x_offset, y), self.font, 0.5, (0, 255, 0), 1)

        # --- COMMAND LEGEND ---
        legend = "[Q] ABORT | [D] HUD | [A] ALARM TOGGLE | [S] SELECT TARGETS"
        text_size = cv2.getTextSize(legend, self.font, 0.45, 1)[0]
        cx = (w + self.panel_width - text_size[0]) // 2
        cv2.putText(canvas, legend, (cx, h - 12), self.font, 0.45, (200, 200, 200), 1)

        return canvas

    def _draw_status(self, canvas, text, status, x, y):
        color = (0, 255, 0) if status else (100, 100, 100)
        state_text = "ONLINE" if status else "OFFLINE"
        cv2.putText(canvas, f"{text} : [{state_text}]", (x, y), self.font, 0.5, color, 1)