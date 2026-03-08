import logging
import cv2
from ultralytics import YOLO
import supervision as sv
from config import SystemState
from horizon_engine import HorizonScanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OmniDetector:
    def __init__(self):
        try:
            self.model = YOLO('yolov8n.pt') 
            self.horizon_scanner = HorizonScanner()
            
            # --- SUPERVISION TAKTİKSEL ARAYÜZ MOTORLARI ---
            self.tracker = sv.ByteTrack()
            self.box_annotator = sv.BoxAnnotator(thickness=2)
            self.label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5)
            self.trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30, position=sv.Position.BOTTOM_CENTER)
            
            logger.info("YOLOv8n ve Supervision Motorları Başarıyla Yüklendi")
        except Exception as e:
            logger.error(f"Başlatma hatası: {e}")
            raise RuntimeError(f"Kritik Hata: Dedektör başlatılamadı - {e}") 

    def process(self, frame):
        processed_frame = frame.copy()
        
        if not SystemState.TRACKING_ACTIVE:
            return processed_frame

        try:
            h, w = frame.shape[:2]
            horizon_y = 0

            # 1. UFUK TARAMASI VE GÖRÜNTÜ KESME (ROI)
            if SystemState.HORIZON_SCAN_ACTIVE:
                horizon_y = self.horizon_scanner.get_horizon_y(frame)
                roi_frame = frame[horizon_y:h, 0:w] # Gökyüzünü kırp
                
                # Ufuk hattını ekrana çiz
                cv2.line(processed_frame, (0, horizon_y), (w, horizon_y), (0, 255, 255), 2)
                cv2.putText(processed_frame, "HORIZON LIMIT (SAFE ZONE)", (10, horizon_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            else:
                roi_frame = frame

            # 2. YOLO İLE ALGILAMA (Sadece kesilmiş bölgede)
            results = self.model(roi_frame, imgsz=320, conf=0.45, verbose=False)[0]
            
            # 3. ULTRALYTICS SONUÇLARINI SUPERVISION OBJESİNE ÇEVİR
            detections = sv.Detections.from_ultralytics(results)

            # 4. KOORDİNAT DÜZELTME (Kestiğimiz Y eksenini ana ekrana oturtmak için geri ekliyoruz)
            if horizon_y > 0 and len(detections) > 0:
                detections.xyxy[:, 1] += horizon_y
                detections.xyxy[:, 3] += horizon_y

            # 5. SUPERVISION İLE TAKİP (ByteTrack)
            detections = self.tracker.update_with_detections(detections)

            # 6. TAKTİKSEL ÇİZİMLER (Kutu, Etiket ve İz Bırakma)
            labels = [
                f"#{tracker_id} {results.names[class_id]} %{confidence:.2f}"
                for xyxy, mask, confidence, class_id, tracker_id, data
                in detections
            ]

            processed_frame = self.box_annotator.annotate(scene=processed_frame, detections=detections)
            processed_frame = self.label_annotator.annotate(scene=processed_frame, detections=detections, labels=labels)
            processed_frame = self.trace_annotator.annotate(scene=processed_frame, detections=detections)

            return processed_frame
            
        except Exception as e:
            logger.error(f"Kare işleme hatası: {e}")
            return frame