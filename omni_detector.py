import logging
from ultralytics import YOLO
from config import SystemState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OmniDetector:
    def __init__(self):
        try:
            self.model = YOLO('yolov8n.pt')
            logger.info("YOLOv8n model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8n model: {e}")
            raise RuntimeError(f"Critical: Cannot initialize detector - {e}") 

    def process(self, frame):
        if not SystemState.TRACKING_ACTIVE:
            return frame # Takip kapalıysa ham görüntüyü ver

        try:
            results = self.model.track(frame, persist=True, stream=True, verbose=False, imgsz=320, tracker="bytetrack.yaml")
            processed_frame = frame
            
            for r in results:
                processed_frame = r.plot()
            
            return processed_frame
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return frame