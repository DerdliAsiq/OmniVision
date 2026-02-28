import cv2
import time
import logging
from omni_engine import OmniEngine
from omni_detector import OmniDetector
from omni_ui import TacticalUI
from config import SystemState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("[+] Aelsa-OmniVision V1.2 Başlatılıyor...")
    
    try:
        engine = OmniEngine(source=0)
        detector = OmniDetector()
        ui = TacticalUI()
    except Exception as e:
        logger.error(f"Failed to initialize system components: {e}")
        print(f"[ERROR] System initialization failed: {e}")
        return
    
    engine.start()
    
    # Wait for camera to warm up and provide valid frames
    max_wait = 5  # seconds
    start_time = time.time()
    while engine.get_frame() is None and (time.time() - start_time) < max_wait:
        time.sleep(0.1)
    
    if engine.get_frame() is None:
        logger.error("Camera failed to provide frames after initialization")
        print("[ERROR] Camera initialization failed - no frames available")
        engine.stop()
        return

    window_name = "Aelsa-OmniVision: Tactical Intelligence"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    prev_time = time.time()

    try:
        while True:
            frame = engine.get_frame()
            if frame is None:
                continue
                
            # 1. AI Katmanı (Takip açıksa işler, kapalıysa direkt geçer)
            processed_frame = detector.process(frame)
            
            # 2. FPS Hesaplama
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            # 3. Arayüz Katmanı (Sağdaki Dashboard'u çizer)
            final_frame = ui.draw_dashboard(processed_frame, fps)

            # 4. Görüntüleme
            cv2.imshow(window_name, final_frame)
            
            # --- KLAVYE KONTROLLERİ (HOTKEYS) ---
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('d'): # Dashboard aç/kapat
                SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
            elif key == ord('t'): # AI Tracking aç/kapat
                SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
            elif key == ord('l'): # LiDAR sensörü simülasyonunu aç/kapat
                SystemState.LIDAR_ACTIVE = not SystemState.LIDAR_ACTIVE
            elif key == ord('p'): # Performans paneli aç/kapat
                SystemState.SHOW_PERFORMANCE = not SystemState.SHOW_PERFORMANCE

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("[!] Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
        print(f"[ERROR] Unexpected error: {e}")
    finally:
        if 'engine' in locals():
            engine.stop()
        cv2.destroyAllWindows()
        print("[+] Sistem Güvenli Şekilde Kapatıldı.")

if __name__ == "__main__":
    main()