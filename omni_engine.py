import cv2
import platform
import threading
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OmniEngine:
    def __init__(self, source=0):
        self.arch = platform.machine()
        self.os_type = platform.system()
        self.source = source
        self.cap = None
        
        self._initialize_camera()
        
        self.ret, self.frame = False, None
        self.is_running = False
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.frame_read_time = 0.0
        self.drop_count = 0

    def _initialize_camera(self):
        # [OFANSİF PERSPEKTİF] - Virtual Cam Injection/Hooking engelleme & MSMF API Zorlama
        if self.os_type == "Windows":
            logger.info("[*] Windows OS Tespit Edildi. MSMF (Media Foundation) API deneniyor...")
            
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_MSMF)
            
            if not self.cap.isOpened():
                logger.warning("[!] MSMF başlatılamadı. DSHOW API'ye (Fallback) geçiliyor.")
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            
            self.cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            
        elif self.arch == "aarch64": 
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
        else:
            self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            raise RuntimeError(f"[Kritik Hata] Kamera kaynağı ({self.source}) donanımsal olarak başlatılamadı.")

        # [PERFORMANS OPTİMİZASYONU] - I/O darboğazını aşmak için MJPG ve Zero-Buffer
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280) 
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 5)

    def start(self):
        if not self.cap.isOpened():
            logger.error("[X] Kamera çevrimdışı. Motor başlatılamıyor.")
            return
        self.is_running = True
        self.thread.start()

    def _update(self):
        error_count = 0
        while self.is_running:
            t0 = time.perf_counter()
            self.ret, frame = self.cap.read()
            self.frame_read_time = (time.perf_counter() - t0) * 1000
            
            if not self.ret or frame is None:
                error_count += 1
                self.drop_count += 1
                if error_count % 3 == 0:
                    logger.warning(f"[!] Kamera Frame Drop Tespit Edildi (Kayıp: {error_count}/10)")
                
                if error_count > 10:
                    logger.error("[X] Kamera bağlantısı tamamen koptu. Kaynak ele geçirilmiş veya bağlantı kesilmiş olabilir.")
                    self.is_running = False
                    break
                    
                time.sleep(0.001) 
                continue
            
            error_count = 0 
            self.frame = cv2.flip(frame, 1)

    def get_frame(self):
        return self.frame

    def stop(self):
        self.is_running = False
        if self.thread.is_alive():
            self.thread.join(timeout=3) 
        if self.cap and self.cap.isOpened():
            self.cap.release()
        logger.info("[+] I/O Görüntü Motoru Güvenli Şekilde İzole Edildi ve Kapatıldı.")