import logging
import cv2
from pathlib import Path
from config import SystemState
from horizon_engine import HorizonScanner
import supervision as sv

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

class OmniDetector:
    def __init__(self, model_path="yolov8x.pt"):
        self.model = None
        self.horizon_scanner = HorizonScanner()
        
        try:
            if YOLO is None:
                raise RuntimeError("ultralytics package is not installed")

            self.model = YOLO(model_path)
            
            self.tracker = sv.ByteTrack()
            self.box_annotator = sv.BoxAnnotator(thickness=2)
            self.label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5)
            self.trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30, position=sv.Position.BOTTOM_CENTER)
            
            logger.info(f"YOLOv8x ve Supervision Motorları Başarıyla Yüklendi")
        except Exception as e:
            logger.error(f"Başlatma hatası: {e}")
            raise RuntimeError(f"Kritik Hata: Dedektör başlatılamadı - {e}") from e

    def process(self, frame):
        processed_frame = frame.copy()
        threats = [] 
        
        if not SystemState.TRACKING_ACTIVE or self.model is None:
            return processed_frame, threats

        try:
            h, w = frame.shape[:2]
            horizon_y = 0

            if SystemState.HORIZON_SCAN_ACTIVE:
                horizon_y = self.horizon_scanner.get_horizon_y(frame)
                roi_frame = frame[horizon_y:h, 0:w] 
                
                cv2.line(processed_frame, (0, horizon_y), (w, horizon_y), (0, 255, 255), 2)
                cv2.putText(processed_frame, "HORIZON LIMIT (SAFE ZONE)", (10, horizon_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            else:
                roi_frame = frame

            results = self.model(roi_frame, imgsz=320, conf=0.45, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)

            if horizon_y > 0 and len(detections) > 0:
                detections.xyxy[:, 1] += horizon_y
                detections.xyxy[:, 3] += horizon_y

            detections = self.tracker.update_with_detections(detections)

            labels = [
                f"#{tracker_id} {results.names[class_id]} %{confidence:.2f}"
                for xyxy, mask, confidence, class_id, tracker_id, data in detections
            ]

            processed_frame = self.box_annotator.annotate(scene=processed_frame, detections=detections)
            processed_frame = self.label_annotator.annotate(scene=processed_frame, detections=detections, labels=labels)
            processed_frame = self.trace_annotator.annotate(scene=processed_frame, detections=detections)

            for i in range(len(detections)):
                box = detections.xyxy[i].tolist()
                tracker_id = int(detections.tracker_id[i]) if detections.tracker_id[i] is not None else 0
                threats.append({
                    'id': tracker_id,
                    'label': results.names[detections.class_id[i]],
                    'confidence': float(detections.confidence[i]),
                    'bbox': box
                })

        except Exception as e:
            logger.error(f"Detection failed: {e}")

        return processed_frame, threats