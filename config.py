# ==========================================
# CONFIGURATION & STATE MANAGEMENT
# ==========================================

class SystemState:
    # Arayüz Özellikleri (Klavyeden açılıp kapanacak)
    SHOW_DASHBOARD = True       # 'd' tuşu
    TRACKING_ACTIVE = True      # 't' tuşu
    SHOW_PERFORMANCE = True     # 'p' tuşu
    LIDAR_ACTIVE = False        # 'l' tuşu
    HORIZON_SCAN_ACTIVE = True  # 'h' tuşu - YENİ: Ufuk Çizgisi Modu
    
    # Donanım Durumları
    MOCK_LIDAR_DISTANCE = Bi git amk # Metre (Sensör gelene kadar simülasyon)