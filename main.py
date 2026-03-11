import cv2
import time
import logging
import threading
import uvicorn
from omni_engine import OmniEngine
from omni_detector import OmniDetector
from omni_ui import TacticalUI
from omni_database import OmniDatabase
from config import SystemState
from target_menu import open_target_menu
import tactical_web_dashboard # Web C2 Modülü

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

def run_web_server():
    """Arka planda C2 Komuta Kontrol sunucusunu (FastAPI) ayağa kaldırır."""
    logger.info("[+] C2 Web Sunucusu Başlatılıyor: http://0.0.0.0:8000")
    # Log seviyesini error yaptık ki terminali spagettiye çevirmesin
    uvicorn.run(tactical_web_dashboard.app, host="0.0.0.0", port=8000, log_level="error")

def main():
    print("[+] OmniVision V1.2 Başlatılıyor...")
    
    # --- WEB SUNUCUSUNU DAEMON THREAD İLE BAŞLAT ---
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    try:
        engine = OmniEngine(source=0)
        detector = OmniDetector()
        ui = TacticalUI()
        db = OmniDatabase() 
    except Exception as e:
        logger.error(f"Failed to initialize system components: {e}")
        return
    
    engine.start()
    
    max_wait = 5  
    start_time = time.time()
    while engine.get_frame() is None and (time.time() - start_time) < max_wait:
        time.sleep(0.1)
    
    if engine.get_frame() is None:
        logger.error("Camera failed to provide frames after initialization")
        engine.stop()
        if 'db' in locals(): db.stop()
        return

    window_name = "OmniVision: Tactical Intelligence"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    prev_time = time.time()

    try:
        while True:
            frame = engine.get_frame()
            if frame is None:
                continue
                
            processed_frame, threats = detector.process(frame)
            
            for t in threats:
                db.log_threat(
                    object_id=t['id'],
                    label=t['label'],
                    confidence=t['confidence'],
                    bbox=t['bbox']
                )
            
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            final_frame = ui.draw_dashboard(processed_frame, fps)
            
            # --- YENİ: CANLI YAYINI WEB SUNUCUSUNA GÖNDER ---
            tactical_web_dashboard.update_video_frame(final_frame)
            
            cv2.imshow(window_name, final_frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            # Bilgisayar başındaki fiziksel kısayollar (Hala aktif!)
            if key == ord('q'): break
            elif key == ord('d'): SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
            elif key == ord('t'): SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
            elif key == ord('l'): SystemState.LIDAR_ACTIVE = not SystemState.LIDAR_ACTIVE
            elif key == ord('p'): SystemState.SHOW_PERFORMANCE = not SystemState.SHOW_PERFORMANCE
            elif key == ord('h'): SystemState.HORIZON_SCAN_ACTIVE = not SystemState.HORIZON_SCAN_ACTIVE
            elif key == ord('a'): 
                SystemState.ALARM_MODE = not SystemState.ALARM_MODE
                print(f"[*] RADAR DURUMU: {'AKTİF' if SystemState.ALARM_MODE else 'PASİF'}")
            elif key == ord('s'): 
                print("[!] Hedef Seçim Menüsü Açılıyor. Sistem Standby Modunda...")
                open_target_menu()

    except KeyboardInterrupt:
        print("[!] Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        if 'engine' in locals(): engine.stop()
        if 'db' in locals(): db.stop()
        cv2.destroyAllWindows()
        print("[+] Sistem Güvenli Şekilde Kapatıldı.")

if __name__ == "__main__":
    main()