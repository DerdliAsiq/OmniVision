class SystemState:
    # --- RADAR VE HUD DURUMLARI ---
    ALARM_MODE = False
    TRACKING_ACTIVE = True  # T tuşu ile açılıp kapanacak
    SHOW_DASHBOARD = True
    SHOW_PERFORMANCE = True
    
    # --- YAPAY ZEKA GÖRME MATRİSİ ---
    AI_RESOLUTION = 640  # Predator Vision
    
    # --- HEDEFLEME HAFIZASI ---
    ACTIVE_TARGET_IDS = []     
    ACTIVE_TARGET_NAMES = []   
    MODEL_CLASSES = {}         
    
    # --- TEHDİT VE SİSTEM DURUMU ---
    IS_THREAT_DETECTED = False
    IS_AUDIO_PLAYING = False
    
    # --- ANOMALİ (İSTİHBARAT) MOTORU ---
    LOITER_THRESHOLD = 5  
    
    # --- ADLİ BİLİŞİM VE VERİTABANI KONTROLÜ ---
    LOG_COOLDOWN = 3  

    # --- SESLİ KOMUT (VOICE C2) ŞALTERİ ---
    VOICE_COMMANDS_ACTIVE = False  
    
    # --- VERİ SAKLAMA POLİTİKASI (MADDE 5.2) ---
    LOG_RETENTION_DAYS = 1               # Loglar ve fotoğraflar sadece 1 gün tutulacak
    EVIDENCE_DIR = "evidence_captures"   # Kanıt fotoğraflarının kaydedileceği klasör