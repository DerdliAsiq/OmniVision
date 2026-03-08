import cv2
import numpy as np

class HorizonScanner:
    def __init__(self):
        self.blur_kernel = (5, 5)
        self.canny_low = 50
        self.canny_high = 150

    def get_horizon_y(self, frame):
        h, w = frame.shape[:2]
        
        # İşlemci tasarrufu: Görüntüyü küçültüp ufku bul
        small_frame = cv2.resize(frame, (w // 2, h // 2))
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, self.blur_kernel, 0)
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)

        # Hough Transform ile çizgileri bul
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=w//4, maxLineGap=40)

        horizon_y = 0

        if lines is not None:
            horizontal_lines = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Dalga toleransı için açı hesapla
                angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi)
                if angle < 15 or angle > 165: 
                    horizontal_lines.append(line[0])

            if horizontal_lines:
                # Orijinal boyuta geri oranla (* 2)
                avg_y = int(np.mean([max(l[1], l[3]) for l in horizontal_lines])) * 2
                horizon_y = max(0, avg_y - 30) # 30 px güvenlik payı bırak

        return horizon_y