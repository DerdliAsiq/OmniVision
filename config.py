# ==========================================
# CONFIGURATION & STATE MANAGEMENT
# ==========================================

class SystemState:
    SHOW_DASHBOARD = True       
    TRACKING_ACTIVE = True      
    SHOW_PERFORMANCE = True     
    LIDAR_ACTIVE = False        
    HORIZON_SCAN_ACTIVE = True  
    MOCK_LIDAR_DISTANCE = 5.0  

    # ==========================================
    # ERKEN UYARI VE HEDEF SİSTEMİ (V2)
    # ==========================================
    ALARM_MODE = False
    IS_THREAT_DETECTED = False
    IS_AUDIO_PLAYING = False  # Akıllı Ses Kilidi (Smart Lock)

    # YOLO'dan okunan dinamik sınıf haritası (omni_detector dolduracak)
    MODEL_CLASSES = {}

    # Seçili Hedefler (Varsayılan: 0 = Person, 8 = Boat)
    ACTIVE_TARGET_IDS = [0, 8]
    ACTIVE_TARGET_NAMES = ["PERSON", "BOAT"]