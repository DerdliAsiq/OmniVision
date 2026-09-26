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
        # Env ile zorlanabilir: LIDAR_PORT=COM4 / /dev/ttyUSB0 / auto
        try:
            forced = str(getattr(SystemState, "LIDAR_PORT", "auto") or "auto").strip()
        except Exception:
            forced = "auto"
        if forced.lower() not in ("auto", "", "none"):
            return forced
        if serial is None:
            return None
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                desc = str(getattr(p, "description", "") or "").lower()
                dev = str(getattr(p, "device", "") or "").lower()
                if any(kw in desc for kw in ["arduino", "cp210", "ch340", "ftdi", "usb", "serial", "lidar", "sonar"]):
                    return p.device
                # Windows COM veya Linux ttyUSB/ttyACM/ttyAMA: sadece device tam eslesirse.
                if dev.startswith("com") or "ttyusb" in dev or "ttyacm" in dev or "ttyama" in dev:
                    return p.device
        except Exception:
            pass
        # Port bulunamazsa None don (caller simulasyona duser), OS-spesifik tahmin yok.
        return None

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
            baud = int(getattr(SystemState, "LIDAR_BAUD", 115200) or 115200)
        except Exception:
            baud = 115200
        if port:
            try:
                self.ser = serial.Serial(port, baud, timeout=0.5)
                logger.info(f"[*] Seri port bağlandı: {port} @ {baud}")
            except Exception as e:
                logger.warning(f"[!] Seri port ({port}) açılamadı: {e}. Simülasyon modu aktif.")
                self.ser = None
        else:
            logger.info("[*] Seri port bulunamadi, simulasyon modu aktif.")
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
                                    # Mantik disi degerleri ele (0-5000cm aralik).
                                    if 0 <= distance <= 5000 and SystemState.LIDAR_ACTIVE:
                                        SystemState.LIDAR_DISTANCE = distance
                                except ValueError:
                                    pass
                        buffer = lines[-1]
                else:
                    # Simulasyon sadece LIDAR aktifken state'i kirletir.
                    if SystemState.LIDAR_ACTIVE:
                        import random as _rnd
                        base = int((time.time() * 10) % 200 + 30)
                        SystemState.LIDAR_DISTANCE = max(0, base + _rnd.randint(-5, 5))
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
