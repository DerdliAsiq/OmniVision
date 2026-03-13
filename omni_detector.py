import logging
import cv2
import time  
import numpy as np
from config import SystemState
import supervision as sv

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

class OmniDetector:
    def __init__(self, model_path="yolo26x.pt"):
        self.model = None
        self.track_history = {} 
        
        try:
            if YOLO is None:
                raise RuntimeError("ultralytics package is not installed")

            logger.info(f"[*] SİSTEM YÜKSELTİLMESİ: {model_path} İndiriliyor/Yükleniyor...")
            self.model = YOLO(model_path)
            SystemState.MODEL_CLASSES = self.model.names
            
            print("\n" + "="*55)
            print(f"[ 👁️ OMNIVISION ] İSTİHBARAT: PREDATOR ÇEKİRDEĞİ AKTİF")
            print("="*55 + "\n")

            logger.info("[*] Yapay Zeka Isıtılıyor (CUDA FP16 Warm-up)...")
            dummy_frame = np.zeros((SystemState.AI_RESOLUTION, SystemState.AI_RESOLUTION, 3), dtype=np.uint8)
            self.model(dummy_frame, imgsz=SystemState.AI_RESOLUTION, device=0, half=True, verbose=False)
            logger.info("[+] Motor Isındı. Sıfır Gecikme (0 Lag) Sağlandı.")

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
            # Ufuk kesme (ROI) tehlikesi tamamen söküldü, tüm ekran işleniyor
            results = self.model(frame, imgsz=SystemState.AI_RESOLUTION, device=0, half=True, conf=0.45, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)

            if SystemState.ALARM_MODE and len(detections) > 0:
                for cls_id in detections.class_id:
                    if cls_id in SystemState.ACTIVE_TARGET_IDS:
                        SystemState.IS_THREAT_DETECTED = True
                        break

            detections = self.tracker.update_with_detections(detections)

            current_ids = []
            labels = []
            anomaly_boxes = [] 
            anomaly_labels = []

            if detections.tracker_id is not None:
                for i in range(len(detections)):
                    tracker_id = int(detections.tracker_id[i])
                    current_ids.append(tracker_id)
                    
                    if tracker_id not in self.track_history:
                        self.track_history[tracker_id] = time.time()
                    
                    elapsed_time = time.time() - self.track_history[tracker_id]
                    class_name = results.names[detections.class_id[i]].upper()
                    confidence = float(detections.confidence[i])
                    box = detections.xyxy[i]
                    
                    event_type = "STANDARD"
                    if SystemState.ALARM_MODE and detections.class_id[i] in SystemState.ACTIVE_TARGET_IDS:
                        event_type = "ALARM"
                    elif elapsed_time >= SystemState.LOITER_THRESHOLD:
                        event_type = "ANOMALY"

                    if event_type == "ANOMALY":
                        labels.append("") 
                        anomaly_boxes.append(box)
                        anomaly_labels.append(f"[ANOMALY: LOITERING - {int(elapsed_time)}s] {class_name} %{int(confidence*100)}")
                    else:
                        labels.append(f"#{tracker_id} {class_name} %{int(confidence*100)}")
                        
                    threats.append({
                        'id': tracker_id,
                        'label': class_name,
                        'event_type': event_type,
                        'duration_sec': int(elapsed_time),
                        'confidence': confidence,
                        'bbox': box.tolist()
                    })

            ids_to_remove = [t_id for t_id in self.track_history if t_id not in current_ids]
            for t_id in ids_to_remove:
                del self.track_history[t_id]

            processed_frame = self.box_annotator.annotate(scene=processed_frame, detections=detections)
            processed_frame = self.label_annotator.annotate(scene=processed_frame, detections=detections, labels=labels)
            processed_frame = self.trace_annotator.annotate(scene=processed_frame, detections=detections)

            for i, box in enumerate(anomaly_boxes):
                x1, y1, x2, y2 = map(int, box)
                is_orange = int(time.time() * 4) % 2 == 0 
                orange_color = (0, 165, 255) 
                black_color = (15, 15, 15) 
                box_color = orange_color if is_orange else black_color
                txt_bg_color = orange_color if is_orange else black_color
                txt_color = (0, 0, 0) if is_orange else orange_color
                
                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), box_color, 3)
                
                line_len = 20
                thickness = 5
                cv2.line(processed_frame, (x1, y1), (x1 + line_len, y1), box_color, thickness)
                cv2.line(processed_frame, (x1, y1), (x1, y1 + line_len), box_color, thickness)
                cv2.line(processed_frame, (x2, y1), (x2 - line_len, y1), box_color, thickness)
                cv2.line(processed_frame, (x2, y1), (x2, y1 + line_len), box_color, thickness)
                
                label = anomaly_labels[i]
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(processed_frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), txt_bg_color, -1)
                cv2.putText(processed_frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, txt_color, 2)

            if SystemState.ALARM_MODE and SystemState.IS_THREAT_DETECTED:
                is_red = int(time.time() * 6) % 2 == 0 
                strobe_color = (0, 0, 255) if is_red else (10, 10, 10)
                txt_color = (255, 255, 255) if is_red else (0, 0, 255)
                
                for i in range(len(detections)):
                    if detections.class_id[i] in SystemState.ACTIVE_TARGET_IDS:
                        x1, y1, x2, y2 = map(int, detections.xyxy[i])
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), strobe_color, 4)
                        
                        line_len = 30
                        thickness = 6
                        cv2.line(processed_frame, (x1, y1), (x1 + line_len, y1), strobe_color, thickness)
                        cv2.line(processed_frame, (x1, y1), (x1, y1 + line_len), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y1), (x2 - line_len, y1), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y1), (x2, y1 + line_len), strobe_color, thickness)
                        cv2.line(processed_frame, (x1, y2), (x1 + line_len, y2), strobe_color, thickness)
                        cv2.line(processed_frame, (x1, y2), (x1, y2 - line_len), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y2), (x2 - line_len, y2), strobe_color, thickness)
                        cv2.line(processed_frame, (x2, y2), (x2, y2 - line_len), strobe_color, thickness)
                        
                        base_label = results.names[detections.class_id[i]].upper()
                        if detections.tracker_id is not None:
                            tracker_id = int(detections.tracker_id[i])
                            strobe_label = f"#{tracker_id} {base_label} [LOCKED]"
                        else:
                            strobe_label = f"{base_label} [LOCKED]"
                            
                        (tw, th), _ = cv2.getTextSize(strobe_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        cv2.rectangle(processed_frame, (x1, y1 - th - 12), (x1 + tw + 10, y1), strobe_color, -1)
                        cv2.putText(processed_frame, strobe_label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, txt_color, 2)

        except Exception as e:
            logger.error(f"Detection failed: {e}")

        return processed_frame, threats