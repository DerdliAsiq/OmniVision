import cv2
import psutil
import numpy as np  
from config import SystemState

class TacticalUI:
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.color_green = (0, 255, 0)
        self.color_red = (0, 0, 255)
        self.color_white = (255, 255, 255)
        self.panel_width = 320 

    def draw_dashboard(self, frame, fps):
        if not SystemState.SHOW_DASHBOARD:
            return frame

        h, w = frame.shape[:2]
        canvas = np.zeros((h, w + self.panel_width, 3), dtype=np.uint8)
        canvas[0:h, 0:w] = frame
        start_x = w + 20 

        cv2.putText(canvas, "OMNIVISION", (start_x, 40), self.font, 0.7, self.color_red, 2)
        cv2.putText(canvas, "SYSTEM DASHBOARD", (start_x, 70), self.font, 0.5, self.color_white, 1)
        cv2.line(canvas, (start_x, 85), (start_x + 280, 85), self.color_white, 1)

        y_offset = 120

        cv2.putText(canvas, "[SYSTEM MODULES]", (start_x, y_offset), self.font, 0.5, self.color_white, 1)
        y_offset += 30
        self._draw_status(canvas, "Tracking (T)", SystemState.TRACKING_ACTIVE, start_x, y_offset)
        y_offset += 25
        self._draw_status(canvas, "LiDAR Sensor (L)", SystemState.LIDAR_ACTIVE, start_x, y_offset)
        y_offset += 25
        self._draw_status(canvas, "Horizon Scan (H)", SystemState.HORIZON_SCAN_ACTIVE, start_x, y_offset)
        y_offset += 40

        if SystemState.LIDAR_ACTIVE:
            cv2.putText(canvas, "[LIDAR TELEMETRY]", (start_x, y_offset), self.font, 0.5, self.color_white, 1)
            y_offset += 30
            dist_text = f"Distance: {SystemState.MOCK_LIDAR_DISTANCE} m"
            cv2.putText(canvas, dist_text, (start_x, y_offset), self.font, 0.6, (0, 255, 255), 2)
            y_offset += 40

        if SystemState.SHOW_PERFORMANCE:
            cv2.putText(canvas, "[PERFORMANCE METRICS]", (start_x, y_offset), self.font, 0.5, self.color_white, 1)
            y_offset += 30
            
            cpu_usage = psutil.cpu_percent()
            ram_usage = psutil.virtual_memory().percent
            
            cv2.putText(canvas, f"FPS  : {int(fps)}", (start_x, y_offset), self.font, 0.6, self.color_green, 1)
            y_offset += 25
            cv2.putText(canvas, f"CPU  : %{cpu_usage}", (start_x, y_offset), self.font, 0.6, self.color_green, 1)
            y_offset += 25
            cv2.putText(canvas, f"RAM  : %{ram_usage}", (start_x, y_offset), self.font, 0.6, self.color_green, 1)

        return canvas

    def _draw_status(self, canvas, text, status, x, y):
        color = self.color_green if status else self.color_red
        state_text = "ONLINE" if status else "OFFLINE"
        cv2.putText(canvas, f"{text}: {state_text}", (x, y), self.font, 0.5, color, 1)