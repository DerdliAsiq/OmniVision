import cv2
import platform
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OmniEngine:
    def __init__(self, source=0):
        self.arch = platform.machine()
        if self.arch == "aarch64": 
            self.cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        else:
            self.cap = cv2.VideoCapture(source)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280) # Arayüz için çözünürlüğü artırdık
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 5)  # Increased from 2 to prevent frame drops
        
        self.ret, self.frame = False, None
        self.is_running = False
        self.thread = threading.Thread(target=self._update, daemon=True)

    def start(self):
        self.is_running = True
        self.thread.start()

    def _update(self):
        while self.is_running:
            # Görüntüyü geçici bir değişkene (frame) alıyoruz
            self.ret, frame = self.cap.read()
            if not self.ret:
                logger.warning("Camera frame read failed - camera may be disconnected")
                self.is_running = False
                break # Hata varsa döngüyü kır
            
            # --- AYNALAMA (FLIP) OPERASYONU ---
            # 1 parametresi görüntüyü yatay olarak (sağ-sol) ters çevirir
            self.frame = cv2.flip(frame, 1)

    def get_frame(self):
        return self.frame

    def stop(self):
        self.is_running = False
        self.thread.join(timeout=5)  # Prevent indefinite hang
        if self.thread.is_alive():
            logger.warning("Camera thread did not exit cleanly within timeout")
        self.cap.release()
        self.cap.release()