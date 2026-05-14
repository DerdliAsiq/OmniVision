import threading
import logging
import time
from config import SystemState

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

logger = logging.getLogger("OmniVision")

class OmniLidar:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.ser = None

    def _find_serial_port(self):
        if serial is None:
            return None
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if any(kw in p.description.lower() for kw in ["arduino", "cp210", "ch340", "ftdi", "usb", "serial", "lidar", "sonar"]):
                    return p.device
                if any(kw in p.device.lower() for kw in ["com", "ttyusb", "ttyama"]):
                    return p.device
        except Exception:
            pass
        return "COM3"

    def start(self):
        if serial is None:
            logger.warning("[!] pyserial paketi eksik. LiDAR motoru pasif.")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        logger.info("[+] LiDAR/Sonar Motoru Başlatıldı.")

    def _read_loop(self):
        port = self._find_serial_port()
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.5)
            logger.info(f"[*] Seri port bağlandı: {port}")
        except Exception as e:
            logger.warning(f"[!] Seri port ({port}) açılamadı: {e}. Simülasyon modu aktif.")
            self.ser = None

        buffer = ""
        while self.is_running:
            try:
                if self.ser and self.ser.is_open:
                    raw = self.ser.read(64).decode("utf-8", errors="ignore")
                    buffer += raw
                    if "\n" in buffer:
                        lines = buffer.split("\n")
                        for line in lines[:-1]:
                            line = line.strip()
                            if line:
                                try:
                                    distance = int(line.replace("cm", "").strip())
                                    SystemState.LIDAR_DISTANCE = distance
                                except ValueError:
                                    pass
                        buffer = lines[-1]
                else:
                    SystemState.LIDAR_DISTANCE = int((time.time() * 10) % 200 + 30)
                    time.sleep(0.5)
            except Exception:
                time.sleep(0.5)

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        SystemState.LIDAR_DISTANCE = None
        logger.info("[+] LiDAR Motoru Güvenli Şekilde Kapatıldı.")
