import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class SystemState:
    # [SIFIR HATA] Çapraz platform uyumlu mutlak dizin yönetimi
    BASE_DIR = Path(__file__).parent.absolute()
    EVIDENCE_DIR = str(BASE_DIR / "evidence")
    
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

    # LiDAR/Sonar Mesafe Sensörü
    LIDAR_ACTIVE = False
    LIDAR_DISTANCE = None
    LIDAR_PORT = "auto"

    # Polygon Zone (Sanal Çit) Yapılandırması
    POLYGON_ZONES_ACTIVE = False
    POLYGON_ZONES = [
        {
            "name": "GÜVENLİ_BÖLGE",
            "polygon": [(200, 200), (440, 200), (440, 440), (200, 440)],
            "color": (0, 255, 255)
        }
    ]
    ZONE_VIOLATIONS = []

    DEBUG_MODE = False