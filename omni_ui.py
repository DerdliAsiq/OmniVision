import cv2
import psutil
import numpy as np
import time
import threading
import os
import logging
import subprocess
from datetime import datetime

try:
    from config import SystemState
except ImportError:
    pass

class TacticalUI:
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.alert_font = cv2.FONT_HERSHEY_DUPLEX
        self.panel_width = 380
        self.alarm_file = "alarm.mp3"
        
        self.CLR_BG = (18, 18, 18)
        self.CLR_ACCENT = (255, 191, 0)
        self.CLR_NEON_G = (120, 255, 0)
        self.CLR_NEON_R = (60, 60, 255)
        self.CLR_TEXT = (230, 230, 230)
        self.CLR_SUBTEXT = (150, 150, 150)
        self.CLR_BORDER = (50, 50, 50)
        
        self.start_time = time.time()
        self.pulse_val = 0
        self.scan_line_y = 0
        
        # OPTİMİZASYON: Statik Çizim Önbelleği
        self.static_canvas = None
        self.last_dim = None
        
        if not os.path.exists(self.alarm_file):
            logging.warning(f"[{self.alarm_file}] bulunamadı!")

    def _play_alarm_sound(self):
        if SystemState.IS_AUDIO_PLAYING: return
        SystemState.IS_AUDIO_PLAYING = True 
        if os.path.exists(self.alarm_file):
            try: subprocess.run(["mpg123", "-q", self.alarm_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass
        else: print("\a", end="", flush=True); time.sleep(1)
        SystemState.IS_AUDIO_PLAYING = False 

    def _build_static_canvas(self, h, w):
        """Ağır CPU işlemi gerektiren tüm arka planı SADECE 1 KEZ çizer ve hafızaya alır."""
        canvas = np.zeros((h, w + self.panel_width, 3), dtype=np.uint8)
        panel_x = w
        cv2.rectangle(canvas, (panel_x, 0), (panel_x + self.panel_width, h), (12, 12, 12), -1)
        cv2.line(canvas, (panel_x, 0), (panel_x, h), (40, 40, 40), 1)

        def draw_glass(y, height, title):
            x = panel_x + 15
            cv2.rectangle(canvas, (x, y), (x + self.panel_width - 30, y + height), self.CLR_BG, -1)
            cv2.rectangle(canvas, (x, y), (x + self.panel_width - 30, y + height), self.CLR_BORDER, 1)
            l = 15
            cv2.line(canvas, (x, y), (x + l, y), self.CLR_ACCENT, 2)
            cv2.line(canvas, (x, y), (x, y + l), self.CLR_ACCENT, 2)
            cv2.line(canvas, (x + self.panel_width - 30, y + height), (x + self.panel_width - 30 - l, y + height), self.CLR_ACCENT, 2)
            cv2.line(canvas, (x + self.panel_width - 30, y + height), (x + self.panel_width - 30, y + height - l), self.CLR_ACCENT, 2)
            cv2.putText(canvas, title, (x + 10, y - 8), self.font, 0.45, self.CLR_ACCENT, 1, cv2.LINE_AA)

        draw_glass(115, 110, "TARGET ACQUISITION")
        draw_glass(265, 100, "SYSTEM MODULES")
        if SystemState.SHOW_PERFORMANCE:
            draw_glass(405, 150, "DIAGNOSTICS")

        footer_h = 45
        cv2.rectangle(canvas, (0, h - footer_h), (w + self.panel_width, h), (10, 10, 10), -1)
        cv2.line(canvas, (0, h - footer_h), (w + self.panel_width, h - footer_h), (40, 40, 40), 1)
        controls = "[Q] ABORT | [S] TARGETS | [A] ALARM | [D] HUD | [T] TRACK | [V] VOICE"
        ts = cv2.getTextSize(controls, self.font, 0.4, 1)[0]
        cv2.putText(canvas, controls, ((w + self.panel_width - ts[0]) // 2, h - 18), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)

        return canvas

    def draw_dashboard(self, frame, fps):
        h, w = frame.shape[:2]
        elapsed = time.time() - self.start_time
        self.pulse_val = (np.sin(elapsed * 5) + 1) / 2 
        
        if SystemState.IS_THREAT_DETECTED:
            if not SystemState.IS_AUDIO_PLAYING:
                threading.Thread(target=self._play_alarm_sound, daemon=True).start()
            alpha = self.pulse_val * 0.4
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), self.CLR_NEON_R, 15)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            
            warn_msg = "!! CRITICAL THREAT DETECTED !!"
            ts = cv2.getTextSize(warn_msg, self.alert_font, 1.0, 2)[0]
            tx, ty = (w - ts[0]) // 2, 80
            cv2.rectangle(frame, (tx-20, ty-45), (tx+ts[0]+20, ty+20), (0,0,180), -1)
            cv2.putText(frame, warn_msg, (tx, ty), self.alert_font, 1.0, (255,255,255), 2, cv2.LINE_AA)

        if not SystemState.SHOW_DASHBOARD:
            return frame

        # Önbelleği Oluştur veya Doğrudan Kullan
        if self.static_canvas is None or self.last_dim != (h, w):
            self.static_canvas = self._build_static_canvas(h, w)
            self.last_dim = (h, w)

        # Kamera Görüntüsünü Statik Şablonun İçine Yapıştır
        canvas = self.static_canvas.copy()
        canvas[0:h, 0:w] = frame
        
        panel_x = w
        x_off = panel_x + 25
        
        # Sadece Değişen Metinleri ve Animasyonları Çiz
        cv2.putText(canvas, "OMNIVISION", (x_off, 35), self.font, 0.75, self.CLR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(canvas, "TACTICAL OS v2.1", (x_off + 155, 35), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        cv2.putText(canvas, datetime.now().strftime("%Y-%m-%d  %H:%M:%S"), (x_off, 65), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        
        targets = ", ".join(SystemState.ACTIVE_TARGET_NAMES) if SystemState.ACTIVE_TARGET_NAMES else "CLEAR"
        if len(targets) > 28: targets = targets[:25] + "..."
        t_color = self.CLR_NEON_R if SystemState.ACTIVE_TARGET_NAMES else self.CLR_NEON_G
        cv2.putText(canvas, "ACTIVE SCAN:", (x_off, 150), self.font, 0.45, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        cv2.putText(canvas, targets, (x_off + 110, 150), self.font, 0.45, t_color, 1, cv2.LINE_AA)
        
        radar_st = "ENGAGED" if SystemState.ALARM_MODE else "STANDBY"
        radar_clr = self.CLR_ACCENT if SystemState.ALARM_MODE else self.CLR_SUBTEXT
        cv2.putText(canvas, "RADAR MODE:", (x_off, 185), self.font, 0.45, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"[{radar_st}]", (x_off + 110, 185), self.font, 0.45, radar_clr, 2, cv2.LINE_AA)

        def draw_led(x, y, label, active):
            color = self.CLR_NEON_G if active else (80, 80, 80)
            if active:
                cv2.circle(canvas, (x, y), 6, color, -1, cv2.LINE_AA)
                cv2.circle(canvas, (x, y), 9, color, 1, cv2.LINE_AA)
            else:
                cv2.circle(canvas, (x, y), 5, color, -1, cv2.LINE_AA)
            cv2.putText(canvas, label, (x + 20, y + 5), self.font, 0.45, self.CLR_TEXT, 1, cv2.LINE_AA)
            cv2.putText(canvas, "ONLINE" if active else "OFFLINE", (x + 180, y + 5), self.font, 0.4, color, 1, cv2.LINE_AA)

        draw_led(x_off + 5, 300, "Tracking (T)", SystemState.TRACKING_ACTIVE)
        draw_led(x_off + 5, 335, "Voice C2 (V)", SystemState.VOICE_COMMANDS_ACTIVE)

        if SystemState.SHOW_PERFORMANCE:
            cv2.putText(canvas, f"ENGINE FPS: {int(fps)}", (x_off, 440), self.font, 0.45, self.CLR_NEON_G, 1, cv2.LINE_AA)
            def draw_bar(y_pos, label, val, clr):
                cv2.putText(canvas, label, (x_off, y_pos - 10), self.font, 0.4, self.CLR_SUBTEXT, 1, cv2.LINE_AA)
                cv2.rectangle(canvas, (x_off, y_pos), (x_off + 240, y_pos + 8), (40, 40, 40), -1)
                cv2.rectangle(canvas, (x_off, y_pos), (x_off + int((val/100)*240), y_pos + 8), clr, -1)
                cv2.putText(canvas, f"{int(val)}%", (x_off + 250, y_pos + 8), self.font, 0.4, clr, 1, cv2.LINE_AA)
            
            draw_bar(485, "CPU LOAD", psutil.cpu_percent(), self.CLR_ACCENT)
            draw_bar(530, "MEMORY", psutil.virtual_memory().percent, self.CLR_NEON_G)

        self.scan_line_y = (self.scan_line_y + 4) % h
        overlay = canvas.copy()
        cv2.line(overlay, (0, self.scan_line_y), (w, self.scan_line_y), self.CLR_ACCENT, 1)
        cv2.addWeighted(overlay, 0.1, canvas, 0.9, 0, canvas)

        return canvas