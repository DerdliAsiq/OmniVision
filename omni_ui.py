import cv2
import psutil
import numpy as np
import time
import threading
import os
import logging
import subprocess
from datetime import datetime

# config importunu güvenli hale getiriyoruz
try:
    from config import SystemState
except ImportError:
    class SystemState:
        ALARM_MODE = False
        TRACKING_ACTIVE = True
        SHOW_DASHBOARD = True
        SHOW_PERFORMANCE = True
        ACTIVE_TARGET_NAMES = []
        IS_THREAT_DETECTED = False
        IS_AUDIO_PLAYING = False
        VOICE_COMMANDS_ACTIVE = False

class TacticalUI:
    def __init__(self):
        # Font Ayarları
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.alert_font = cv2.FONT_HERSHEY_DUPLEX
        self.panel_width = 380
        self.alarm_file = "alarm.mp3"
        
        # --- MODERN RENK PALETİ (B, G, R) ---
        self.CLR_BG = (18, 18, 18)          # Koyu Arka Plan
        self.CLR_ACCENT = (255, 191, 0)     # Elektrik Mavisi
        self.CLR_NEON_G = (120, 255, 0)     # Neon Yeşil
        self.CLR_NEON_R = (60, 60, 255)     # Neon Kırmızı
        self.CLR_TEXT = (230, 230, 230)     # Açık Gri Metin
        self.CLR_SUBTEXT = (150, 150, 150)  # Koyu Gri Alt Metin
        self.CLR_BORDER = (50, 50, 50)      # Panel Sınırları
        
        # Animasyon Değişkenleri
        self.start_time = time.time()
        self.pulse_val = 0
        self.scan_line_y = 0
        
        if not os.path.exists(self.alarm_file):
            logging.warning(f"[{self.alarm_file}] bulunamadı!")

    def _play_alarm_sound(self):
        if SystemState.IS_AUDIO_PLAYING: return
        SystemState.IS_AUDIO_PLAYING = True 
        
        if os.path.exists(self.alarm_file):
            try:
                subprocess.run(["mpg123", "-q", self.alarm_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                try: subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", self.alarm_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except: print("\a", end="", flush=True); time.sleep(1)
        else:
            print("\a", end="", flush=True); time.sleep(1)
        SystemState.IS_AUDIO_PLAYING = False 

    def _draw_glass_panel(self, img, x, y, w, h, title=""):
        """Modern, yarı saydam cam görünümlü panel çizer."""
        overlay = img.copy()
        # Panel Arka Planı
        cv2.rectangle(overlay, (x, y), (x + w, y + h), self.CLR_BG, -1)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
        
        # Panel Sınırları ve Köşe Vurguları
        cv2.rectangle(img, (x, y), (x + w, y + h), self.CLR_BORDER, 1)
        l = 15 # Köşe uzunluğu
        # Sol Üst
        cv2.line(img, (x, y), (x + l, y), self.CLR_ACCENT, 2)
        cv2.line(img, (x, y), (x, y + l), self.CLR_ACCENT, 2)
        # Sağ Alt
        cv2.line(img, (x + w, y + h), (x + w - l, y + h), self.CLR_ACCENT, 2)
        cv2.line(img, (x + w, y + h), (x + w, y + h - l), self.CLR_ACCENT, 2)
        
        if title:
            cv2.putText(img, title.upper(), (x + 10, y - 8), self.font, 0.45, self.CLR_ACCENT, 1, cv2.LINE_AA)

    def _draw_status_led(self, img, x, y, label, active):
        """Modern bir durum göstergesi (LED) çizer."""
        color = self.CLR_NEON_G if active else (80, 80, 80)
        # LED Parlaması
        if active:
            cv2.circle(img, (x, y), 6, color, -1, cv2.LINE_AA)
            cv2.circle(img, (x, y), 9, color, 1, cv2.LINE_AA)
        else:
            # HATA BURADAYDI, DÜZELTİLDİ! (img, x, y) yerine (x, y) yapıldı.
            cv2.circle(img, (x, y), 5, color, -1, cv2.LINE_AA)
            
        cv2.putText(img, label, (x + 20, y + 5), self.font, 0.45, self.CLR_TEXT, 1, cv2.LINE_AA)
        status_text = "ONLINE" if active else "OFFLINE"
        cv2.putText(img, status_text, (x + 180, y + 5), self.font, 0.4, color, 1, cv2.LINE_AA)

    def _draw_metric_bar(self, img, x, y, w, label, value, color):
        """Görsel bir metrik barı çizer."""
        h = 8
        cv2.putText(img, label, (x, y - 10), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        # Arka Plan Barı
        cv2.rectangle(img, (x, y), (x + w, y + h), (40, 40, 40), -1)
        # Doluluk
        bar_w = int((value / 100) * w)
        cv2.rectangle(img, (x, y), (x + bar_w, y + h), color, -1)
        # Yüzde
        cv2.putText(img, f"{int(value)}%", (x + w + 10, y + h), self.font, 0.4, color, 1, cv2.LINE_AA)

    def draw_dashboard(self, frame, fps):
        h, w = frame.shape[:2]
        elapsed = time.time() - self.start_time
        self.pulse_val = (np.sin(elapsed * 5) + 1) / 2 # 0 ile 1 arası dalgalanma
        
        # --- TEHDİT HUD EFEKTİ ---
        if SystemState.IS_THREAT_DETECTED:
            if not SystemState.IS_AUDIO_PLAYING:
                threading.Thread(target=self._play_alarm_sound, daemon=True).start()
            
            # Ekran Kenarı Titremesi
            alpha = self.pulse_val * 0.4
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), self.CLR_NEON_R, 15)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            
            # Merkezi Uyarı
            warn_msg = "!! CRITICAL THREAT DETECTED !!"
            ts = cv2.getTextSize(warn_msg, self.alert_font, 1.0, 2)[0]
            tx, ty = (w - ts[0]) // 2, 80
            cv2.rectangle(frame, (tx-20, ty-45), (tx+ts[0]+20, ty+20), (0,0,180), -1)
            cv2.putText(frame, warn_msg, (tx, ty), self.alert_font, 1.0, (255,255,255), 2, cv2.LINE_AA)

        if not SystemState.SHOW_DASHBOARD:
            return frame

        # --- ANA KANVAS (FRAME + YAN PANEL) ---
        canvas = np.zeros((h, w + self.panel_width, 3), dtype=np.uint8)
        canvas[0:h, 0:w] = frame
        
        # Yan Panel Arka Planı
        panel_x = w
        cv2.rectangle(canvas, (panel_x, 0), (panel_x + self.panel_width, h), (12, 12, 12), -1)
        cv2.line(canvas, (panel_x, 0), (panel_x, h), (40, 40, 40), 1)

        # --- ÜST BİLGİ (HEADER) ---
        curr_y = 35
        x_off = panel_x + 25
        cv2.putText(canvas, "OMNIVISION", (x_off, curr_y), self.font, 0.75, self.CLR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(canvas, "TACTICAL OS v2.1", (x_off + 155, curr_y), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        
        curr_y += 30
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(canvas, now, (x_off, curr_y), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        
        # --- RADAR & TARGETS PANEL ---
        curr_y += 50
        self._draw_glass_panel(canvas, x_off - 10, curr_y, self.panel_width - 30, 110, "Target Acquisition")
        
        target_y = curr_y + 35
        targets = ", ".join(SystemState.ACTIVE_TARGET_NAMES) if SystemState.ACTIVE_TARGET_NAMES else "CLEAR"
        if len(targets) > 28: targets = targets[:25] + "..."
        
        t_color = self.CLR_NEON_R if SystemState.ACTIVE_TARGET_NAMES else self.CLR_NEON_G
        cv2.putText(canvas, "ACTIVE SCAN:", (x_off, target_y), self.font, 0.45, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        cv2.putText(canvas, targets, (x_off + 110, target_y), self.font, 0.45, t_color, 1, cv2.LINE_AA)
        
        target_y += 35
        radar_st = "ENGAGED" if SystemState.ALARM_MODE else "STANDBY"
        radar_clr = self.CLR_ACCENT if SystemState.ALARM_MODE else self.CLR_SUBTEXT
        cv2.putText(canvas, "RADAR MODE:", (x_off, target_y), self.font, 0.45, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"[{radar_st}]", (x_off + 110, target_y), self.font, 0.45, radar_clr, 2, cv2.LINE_AA)

        # --- SYSTEM MODULES PANEL ---
        curr_y += 150
        self._draw_glass_panel(canvas, x_off - 10, curr_y, self.panel_width - 30, 100, "System Modules")
        
        mod_y = curr_y + 35
        self._draw_status_led(canvas, x_off + 5, mod_y, "Tracking (T)", SystemState.TRACKING_ACTIVE)
        mod_y += 35
        self._draw_status_led(canvas, x_off + 5, mod_y, "Voice C2 (V)", SystemState.VOICE_COMMANDS_ACTIVE)

        # --- DIAGNOSTICS PANEL ---
        curr_y += 140
        if SystemState.SHOW_PERFORMANCE:
            self._draw_glass_panel(canvas, x_off - 10, curr_y, self.panel_width - 30, 150, "Diagnostics")
            
            diag_y = curr_y + 35
            cv2.putText(canvas, f"ENGINE FPS: {int(fps)}", (x_off, diag_y), self.font, 0.45, self.CLR_NEON_G, 1, cv2.LINE_AA)
            
            diag_y += 45
            self._draw_metric_bar(canvas, x_off, diag_y, 240, "CPU LOAD", psutil.cpu_percent(), self.CLR_ACCENT)
            diag_y += 45
            self._draw_metric_bar(canvas, x_off, diag_y, 240, "MEMORY", psutil.virtual_memory().percent, self.CLR_NEON_G)

        # --- FOOTER (KONTROLLER) ---
        footer_h = 45
        cv2.rectangle(canvas, (0, h - footer_h), (w + self.panel_width, h), (10, 10, 10), -1)
        cv2.line(canvas, (0, h - footer_h), (w + self.panel_width, h - footer_h), (40, 40, 40), 1)
        
        # [H] HORIZON kaldırıldı, [V] eklendi!
        controls = "[Q] ABORT | [S] TARGETS | [A] ALARM | [D] HUD | [T] TRACK | [V] VOICE"
        ts = cv2.getTextSize(controls, self.font, 0.4, 1)[0]
        cv2.putText(canvas, controls, ((w + self.panel_width - ts[0]) // 2, h - 18), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)

        # --- DEKORATİF TARAMA ÇİZGİSİ (ANIMATED) ---
        self.scan_line_y = (self.scan_line_y + 4) % h
        overlay = canvas.copy()
        cv2.line(overlay, (0, self.scan_line_y), (w, self.scan_line_y), self.CLR_ACCENT, 1)
        cv2.addWeighted(overlay, 0.1, canvas, 0.9, 0, canvas)

        return canvas