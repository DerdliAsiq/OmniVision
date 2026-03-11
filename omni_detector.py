import logging
import cv2
import time  # Flaşör matematiği için eklendi
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
            
            SystemState.MODEL_CLASSES = self.model.names
            
            print("\n" + "="*55)
            print("[ 👁️ OMNIVISION ] İSTİHBARAT: 80 SINIF HAFIZAYA ALINDI")
            print("="*55 + "\n")

            self.tracker = sv.ByteTrack()
            self.box_annotator = sv.BoxAnnotator(thickness=2)
            self.label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5)
            self.trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30, position=sv.Position.BOTTOM_CENTER)
            
        except Exception as e:
            logger.error(f"Başlatma hatası: {e}")
            raise RuntimeError(f"Kritik Hata: Dedektör başlatılamadı - {e}") from e

    def process(self, frame):
        processed_frame = frame.copy()
        threats = [] 
        
        SystemState.IS_THREAT_DETECTED = False

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

            # 1. Tehdit Yargılaması
            if SystemState.ALARM_MODE and len(detections) > 0:
                for cls_id in detections.class_id:
                    if cls_id in SystemState.ACTIVE_TARGET_IDS:
                        SystemState.IS_THREAT_DETECTED = True
                        break

            detections = self.tracker.update_with_detections(detections)

            labels = [
                f"#{tracker_id} {results.names[class_id]} %{confidence:.2f}"
                for xyxy, mask, confidence, class_id, tracker_id, data in detections
            ]

            # 2. Standart Çizimler (Sıradan hedefler için turuncu/sarı kutular)
            processed_frame = self.box_annotator.annotate(scene=processed_frame, detections=detections)
            processed_frame = self.label_annotator.annotate(scene=processed_frame, detections=detections, labels=labels)
            processed_frame = self.trace_annotator.annotate(scene=processed_frame, detections=detections)

            # ========================================================
            # 3. TAKTİKSEL BASKIN (STROBE/FLAŞÖR MOTORU)
            # ========================================================
            if SystemState.ALARM_MODE and SystemState.IS_THREAT_DETECTED:
                # Zaman bazlı saniyede 6 kez değişen renk dalgası (Kırmızı/Siyah)
                is_red = int(time.time() * 6) % 2 == 0 
                strobe_color = (0, 0, 255) if is_red else (10, 10, 10)
                txt_color = (255, 255, 255) if is_red else (0, 0, 255)
                
                for i in range(len(detections)):
                    # SADECE hedeflenen nesnelerin üzerine flaşör atılır, diğerleri standart kalır!
                    if detections.class_id[i] in SystemState.ACTIVE_TARGET_IDS:
                        x1, y1, x2, y2 = map(int, detections.xyxy[i])
                        
                        # A) Standart kutuyu ezen 4px kalınlığında Flaşör Kutusu
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), strobe_color, 4)
                        
                        # B) Hedef Nişangahı (Köşelere atılan kalın taktiksel çizgiler)
                        line_len = 30
                        thickness = 6
                        # Sol Üst
                        cv2.line(processed_frame, (x1, y1), (x1 + line_len, y1), strobe_color, thickness)
                        cv2.line(processed_frame, (x1, y1), (x1, y1 + line_len), strobe_color, thickness)
                        # Sağ Üst
                        cv2.line(processed_frame, (x2, y1), (x2 - line_len, y1), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y1), (x2, y1 + line_len), strobe_color, thickness)
                        # Sol Alt
                        cv2.line(processed_frame, (x1, y2), (x1 + line_len, y2), strobe_color, thickness)
                        cv2.line(processed_frame, (x1, y2), (x1, y2 - line_len), strobe_color, thickness)
                        # Sağ Alt
                        cv2.line(processed_frame, (x2, y2), (x2 - line_len, y2), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y2), (x2, y2 - line_len), strobe_color, thickness)
                        
                        # C) Etiketin arka planını ve yazı rengini kilitlenme hissiyatı ile değiştir
                        label = labels[i]
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        cv2.rectangle(processed_frame, (x1, y1 - th - 12), (x1 + tw + 10, y1), strobe_color, -1)
                        cv2.putText(processed_frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, txt_color, 2)


            # Loglama için tehditleri hazırla
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