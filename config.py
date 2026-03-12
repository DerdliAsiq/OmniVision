class SystemState:
    # --- RADAR VE HUD DURUMLARI ---
    ALARM_MODE = False
    TRACKING_ACTIVE = True
    HORIZON_SCAN_ACTIVE = False
    SHOW_DASHBOARD = True
    SHOW_PERFORMANCE = True
    LIDAR_ACTIVE = False
    
    # --- YAPAY ZEKA GÖRME MATRİSİ ---
    AI_RESOLUTION = 640  # Predator Vision
    
    # --- HEDEFLEME HAFIZASI ---
    ACTIVE_TARGET_IDS = []     # Örn: [0, 67]
    ACTIVE_TARGET_NAMES = []   # Örn: ["PERSON", "CELL PHONE"]
    
    # Model yüklendiğinde otomatik dolacak sözlük (ID: İsim)
    MODEL_CLASSES = {}         
    
    # --- TEHDİT VE SİSTEM DURUMU ---
    IS_THREAT_DETECTED = False
    
    # YENİ: ASENKRON SES KİLİDİ (CRASH ÖNLEYİCİ)
    # Bu kilit, alarm çalarken sistemin üst üste ses açıp çökmesini engeller.
    IS_AUDIO_PLAYING = False