# ==========================================
# CONFIGURATION & STATE MANAGEMENT
# ==========================================

class SystemState:
    # Arayüz Özellikleri (Klavyeden açılıp kapanacak)
    SHOW_DASHBOARD = True       # 'd' tuşu
    TRACKING_ACTIVE = True      # 't' tuşu
    SHOW_PERFORMANCE = True     # 'p' tuşu
    LIDAR_ACTIVE = False        # 'l' tuşu
    HORIZON_SCAN_ACTIVE = True  # 'h' tuşu - Ufuk Çizgisi Modu
    
    # Donanım Durumları
    MOCK_LIDAR_DISTANCE = 5.0  # Metre (sensör gelene kadar simülasyon)