# ==============================================================================
# PROJECT      : Aelsa-OmniVision
# MODULE       : Neural-Shield (detector.py)
# DEVELOPER    : Berzamin Cyber
# LICENSE      : Proprietary - All Rights Reserved
# ==============================================================================

from ultralytics import YOLO
import cv2

class OmniDetector:
    def __init__(self):
        # En hafif ve hızlı model (Pi 5 ve RTX 2050 uyumlu)
        self.model = YOLO('yolov8n.pt') 
        print("[+] Sinirsel Ağ Yüklendi: YOLOv8-Nano Aktif.")

    def detect(self, frame):
        # Nesne tespiti yap (Sadece insan, araç vb. için optimize edilebilir)
        results = self.model(frame, stream=True, verbose=False)
        
        for r in results:
            annotated_frame = r.plot() # Kutuları ve etiketleri çiz
            return annotated_frame
        
        return frame