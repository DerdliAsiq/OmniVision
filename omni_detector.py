import logging
import cv2
import time  
import numpy as np
import os
from config import SystemState
import supervision as sv

try:
    from ultralytics import YOLO
    import torch
except ImportError:
    YOLO = None
    torch = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

class OmniDetector:
    def __init__(self, base_model_name="yolo26x"):
        self.model = None
        self.track_history = {} 
        self.frame_count = 0  
        self.process_interval = 3  
        
        self.last_detections = None
        self.last_labels = []
        self.last_anomaly_boxes = []
        self.last_anomaly_labels = []
        self.last_strobe_boxes = []
        self.last_strobe_labels = []
        self.last_threats = []
        
        if YOLO is None:
            raise RuntimeError("[X] ultralytics paketi bulunamadı.")

        model_path = f"{base_model_name}.engine" if os.path.exists(f"{base_model_name}.engine") else f"{base_model_name}.pt"
        self.model = YOLO(model_path)
        SystemState.MODEL_CLASSES = self.model.names
        
        # [VRAM OPTİMİZASYONU] RTX 2050 4GB VRAM Darboğazı Çözümü
        if torch and torch.cuda.is_available():
            self.device = 0
            self.use_half = True # FP16 Kesinlikle Açık (Bellek Tüketimi Yarıya İner)
            logger.info(f"[*] GPU Aktif. VRAM Tüketimi FP16 (Yarı Hassasiyet) ile optimize edildi.")
        else:
            self.device = "cpu"
            self.use_half = False
            logger.warning("[!] CUDA GPU bulunamadı. Sistem CPU (Ryzen) Modunda.")

        logger.info(f"[*] Predator Çekirdeği Isıtılıyor (Motor: {self.device})...")
        dummy_frame = np.zeros((SystemState.AI_RESOLUTION, SystemState.AI_RESOLUTION, 3), dtype=np.uint8)
        self.model(dummy_frame, imgsz=SystemState.AI_RESOLUTION, device=self.device, half=self.use_half, verbose=False)

        self.tracker = sv.ByteTrack()
        self.box_annotator = sv.BoxAnnotator(thickness=2)
        self.label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5)
        self.trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30, position=sv.Position.BOTTOM_CENTER)

        self.zone_instances = []
        self.zone_annotators = []
        self.zone_masks = []
        for z in SystemState.POLYGON_ZONES:
            polygon = np.array(z["polygon"], dtype=np.int32)
            zone = sv.PolygonZone(polygon=polygon)
            b, g, r = z["color"]
            color = sv.Color(r, g, b)
            annotator = sv.PolygonZoneAnnotator(zone=zone, color=color, thickness=2)
            self.zone_instances.append(zone)
            self.zone_annotators.append(annotator)
            self.zone_masks.append(None)

    def _draw_cached(self, frame):
        if self.last_detections is None:
            return frame

        if len(self.last_labels) != len(self.last_detections):
            return frame.copy()

        processed_frame = frame.copy()
        
        processed_frame = self.box_annotator.annotate(scene=processed_frame, detections=self.last_detections)
        processed_frame = self.label_annotator.annotate(scene=processed_frame, detections=self.last_detections, labels=self.last_labels)
        processed_frame = self.trace_annotator.annotate(scene=processed_frame, detections=self.last_detections)

        for i, box in enumerate(self.last_anomaly_boxes):
            x1, y1, x2, y2 = map(int, box)
            is_orange = int(time.time() * 4) % 2 == 0 
            box_color = (0, 165, 255) if is_orange else (15, 15, 15)
            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), box_color, 3)
            cv2.putText(processed_frame, self.last_anomaly_labels[i], (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

        if SystemState.POLYGON_ZONES_ACTIVE:
            for annotator in self.zone_annotators:
                try:
                    processed_frame = annotator.annotate(scene=processed_frame)
                except Exception:
                    pass

        if SystemState.ALARM_MODE and len(self.last_strobe_boxes) > 0:
            SystemState.IS_THREAT_DETECTED = True
            is_red = int(time.time() * 6) % 2 == 0 
            strobe_color = (0, 0, 255) if is_red else (10, 10, 10)
            for i, box in enumerate(self.last_strobe_boxes):
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), strobe_color, 4)
                cv2.putText(processed_frame, self.last_strobe_labels[i], (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return processed_frame

    def process(self, frame):
        self.frame_count += 1
        SystemState.IS_THREAT_DETECTED = False

        if not SystemState.TRACKING_ACTIVE or self.model is None:
            return frame.copy(), []

        # [PERFORMANS] Her karede inferance yapmayı engelle, önbellektekini çiz
        if self.frame_count % self.process_interval != 0 and self.last_detections is not None:
            return self._draw_cached(frame), self.last_threats

        try:
            results = self.model(frame, imgsz=SystemState.AI_RESOLUTION, device=self.device, half=self.use_half, conf=0.45, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = self.tracker.update_with_detections(detections)

            if SystemState.POLYGON_ZONES_ACTIVE:
                SystemState.ZONE_VIOLATIONS.clear()
                for zi, zone in enumerate(self.zone_instances):
                    try:
                        self.zone_masks[zi] = zone.trigger(detections=detections)
                    except Exception:
                        self.zone_masks[zi] = None

            current_ids = []
            self.last_labels, self.last_anomaly_boxes, self.last_anomaly_labels = [], [], []
            self.last_strobe_boxes, self.last_strobe_labels, self.last_threats = [], [], []

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
                    
                    in_zone = False
                    if SystemState.POLYGON_ZONES_ACTIVE:
                        for mask in self.zone_masks:
                            try:
                                if mask is not None and i < len(mask) and mask[i]:
                                    in_zone = True
                                    break
                            except Exception:
                                pass
                    
                    event_type = "STANDARD"
                    if in_zone or (SystemState.ALARM_MODE and detections.class_id[i] in SystemState.ACTIVE_TARGET_IDS):
                        event_type = "ALARM"
                        if in_zone:
                            SystemState.ZONE_VIOLATIONS.append(tracker_id)
                    elif elapsed_time >= SystemState.LOITER_THRESHOLD:
                        event_type = "ANOMALY"

                    if event_type == "ANOMALY":
                        self.last_labels.append("") 
                        self.last_anomaly_boxes.append(box)
                        self.last_anomaly_labels.append(f"[ANOMALY: {int(elapsed_time)}s] {class_name}")
                    else:
                        self.last_labels.append(f"#{tracker_id} {class_name} %{int(confidence*100)}")
                        
                    if event_type == "ALARM":
                        self.last_strobe_boxes.append(box)
                        self.last_strobe_labels.append(f"#{tracker_id} {class_name} [LOCKED]")

                    self.last_threats.append({
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

            self.last_detections = detections

        except Exception as e:
            logger.error(f"Detection failed: {e}")

        # [SIFIR HATA & VRAM İZOLASYONU] OOM (Out of Memory) Koruması
        if self.frame_count % 60 == 0 and torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

        return self._draw_cached(frame), self.last_threats