import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Windows konsolu (cp1254) emoji/Turkce karakterlerde patlar; tum uygulamayi UTF-8'e zorla.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

class SystemState:
    # Proje versiyonu ve kanonik YOLO modeli (tek kaynak - bkz. __init__.py, omni_detector.py, test_project.py)
    VERSION = "2.0"
    MODEL_NAME = "yolo26x"

    # [SIFIR HATA] Çapraz platform uyumlu mutlak dizin yönetimi
    BASE_DIR = Path(__file__).parent.absolute()
    # Kanit fotograflari: repo'daki evidence_captures/ klasoru ile ayni (tek kaynak).
    EVIDENCE_DIR = str(BASE_DIR / "evidence_captures")
    # Video analiz klasoru: kullanicinin attigi videolar buradan okunur (tek kaynak).
    VIDEO_DIR = str(BASE_DIR / "Video_Analiz")
    SUPPORTED_VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv")
    # Veritabani dosyasi: CWD'ye bagli goreceli yol degil, BASE_DIR'e sabitli mutlak yol.
    # Gecmis surumdeki CWD-relative "tactical_vision_v2.db" ile uyumluluk icin
    # OmniDatabase acilista eski CWD kopyasini tasiyabilir (bkz. omni_database.py).
    DB_NAME = "tactical_vision_v2.db"
    DB_PATH = str(BASE_DIR / DB_NAME)

    # Aktif goruntu kaynagi: "camera" | "video" | "youtube-vod" | "youtube-live" | "rtsp" | "stream"
    # Not: eski "youtube"/"stream" degerleri geriye donuk kabul edilir.
    SOURCE_TYPE = "camera"
    CURRENT_SOURCE = "0"
    CURRENT_SOURCE_LABEL = "CAM 0"

    # Playback / transport durumu (OmniEngine tarafindan guncellenir)
    PLAY_PAUSED = False
    PLAY_POS_SEC = 0.0
    PLAY_DUR_SEC = 0.0
    SEEKABLE = False

    # Asenkron gecis durumu: eski frame ekranda kalir, isci thread acar.
    CONNECTING = False
    CONNECTING_LABEL = ""
    CONNECT_ERROR = ""
    
    LOG_RETENTION_DAYS = 1
    LOG_COOLDOWN = 3.0  # [YAMA] Veritabanı darboğazını ve çökmeyi engelleyen bekleme süresi
    
    MODEL_CLASSES = {}
    ALARM_MODE = False
    TRACKING_ACTIVE = True
    SHOW_DASHBOARD = True
    VOICE_COMMANDS_ACTIVE = False
    IS_THREAT_DETECTED = False
    IS_AUDIO_PLAYING = False
    ACTIVE_TARGET_IDS = []
    ACTIVE_TARGET_NAMES = []
    SHOW_PERFORMANCE = True
    AI_RESOLUTION = 640
    LOITER_THRESHOLD = 300

    C2_USERNAME = os.getenv("C2_USERNAME", "admin")
    C2_PASSWORD = os.getenv("C2_PASSWORD", "1234")
    # C2'yi LAN'a acmak icin acik onay gerekir: C2_ALLOW_LAN=1.
    # Varsayilan admin/1234 ile LAN'a acilma main.py'de engellenir.
    C2_ALLOW_LAN = os.getenv("C2_ALLOW_LAN", "0") == "1"
    C2_HOST_FALLBACK = "127.0.0.1"
    C2_PORT = int(os.getenv("C2_PORT", "8000") or 8000)

    # LiDAR/Sonar Mesafe Sensörü
    LIDAR_ACTIVE = False
    LIDAR_DISTANCE = None
    LIDAR_PORT = os.getenv("LIDAR_PORT", "auto")
    LIDAR_BAUD = int(os.getenv("LIDAR_BAUD", "115200") or 115200)

    # Detector / tracker ayarlari (tek kaynak)
    PROCESS_INTERVAL = int(os.getenv("PROCESS_INTERVAL", "3") or 3)

    # Polygon Zone (Sanal Çit) Yapılandırması
    # Not: koordinatlar 1280x720 referans cerceveye gore olceklenir
    # (detector giris cozunurlugu degisse bile oran korunur).
    POLYGON_ZONES_ACTIVE = False
    POLYGON_ZONES = [
        {
            "name": "GÜVENLİ_BÖLGE",
            "polygon": [(320, 180), (960, 180), (960, 620), (320, 620)],
            "color": (0, 255, 255)
        }
    ]
    ZONE_VIOLATIONS = []

    DEBUG_MODE = False