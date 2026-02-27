# ==============================================================================
# PROJECT      : Aelsa-OmniVision
# VERSION      : 1.0.0
# DEVELOPER    : Berzamin Cyber
# DIVISION     : AELSA Defence (AELSA Technologies)
# LICENSE      : Proprietary - All Rights Reserved
# DESCRIPTION  : High-Performance Hardware-Aware Vision Engine
# ==============================================================================

import cv2
import platform
import threading
import time
import sys

class OmniEngine:
    def __init__(self, source=0):
        self.device_name = platform.node()
        self.arch = platform.machine()
        self.os_type = platform.system()
        
        print(f"[+] Aelsa-OmniVision Başlatılıyor...")
        print(f"[*] Operatör: Berzamin Cyber")
        print(f"[*] Donanım: {self.os_type} ({self.arch})")

        # Donanım Odaklı Kamera Yapılandırması
        if self.arch == "aarch64": # Raspberry Pi 5
            print("[!] Raspberry Pi 5 Algılandı. V4L2 ve Libcamera optimizasyonu aktif.")
            self.cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        else: # PC / RTX 2050
            print("[!] PC/İş İstasyonu Algılandı. DirectShow/MSMF aktif.")
            self.cap = cv2.VideoCapture(source)

        # Buffer'ı (Tampon) küçült, gerçek zamanlılığı artır
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        
        self.ret = False
        self.frame = None
        self.is_running = False
        
        # Threading: Görüntü yakalamayı ana iş parçacığından ayır (Lag Killer)
        self.thread = threading.Thread(target=self._update, args=())
        self.thread.daemon = True

    def start(self):
        self.is_running = True
        self.thread.start()
        print("[+] Görüntü Yakalama Thread'i Aktif.")

    def _update(self):
        while self.is_running:
            self.ret, self.frame = self.cap.read()
            if not self.ret:
                print("[!] Kamera Akışı Kesildi.")
                self.is_running = False
                break

    def get_frame(self):
        return self.frame

    def stop(self):
        self.is_running = False
        self.thread.join()
        self.cap.release()
        cv2.destroyAllWindows()
        print("[+] Sistem Güvenli Şekilde Kapatıldı.")

if __name__ == "__main__":
    # Test Modu
    engine = OmniEngine()
    engine.start()
    
    time.sleep(2) # Sistemin ısınması için süre ver
    
    try:
        while True:
            frame = engine.get_frame()
            if frame is not None:
                # Berzamin Cyber - Görüntü Buraya Gelecek
                cv2.imshow("Aelsa-OmniVision: Tactical View", frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()