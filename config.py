# ==========================================
# CONFIGURATION & STATE MANAGEMENT
# ==========================================

class SystemState:
    # Arayüz Özellikleri (Klavyeden açılıp kapanacak)
    SHOW_DASHBOARD = True     # 'd' tuşu
    TRACKING_ACTIVE = True    # 't' tuşu
    SHOW_PERFORMANCE = True   # 'p' tuşu
    LIDAR_ACTIVE = False      # 'l' tuşu
    
    # Donanım Durumları
    MOCK_LIDAR_DISTANCE = 4.5 # Metre (Sensör gelene kadar simülasyon)