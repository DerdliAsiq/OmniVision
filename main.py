import cv2
import time
import logging
import threading
import uvicorn
import os
from omni_engine import OmniEngine
from omni_detector import OmniDetector
from omni_ui import TacticalUI
from omni_database import OmniDatabase
from omni_voice import OmniVoice 
from config import SystemState
from target_menu import open_target_menu
import tactical_web_dashboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

def run_web_server():
    logger.info("[+] C2 Web Sunucusu Başlatılıyor: http://0.0.0.0:8000")
    uvicorn.run(tactical_web_dashboard.app, host="0.0.0.0", port=8000, log_level="error")

# OPTİMİZASYON: Görüntü Kaydetme İşlemini Ana Döngüden Koparan Gölge Fonksiyon
def save_evidence_async(img_path, frame_copy):
    cv2.imwrite(img_path, frame_copy)

def main():
    print("[+] OmniVision V1.3 Başlatılıyor (Voice C2 Devrede)...")
    
    if not os.path.exists(SystemState.EVIDENCE_DIR):
        os.makedirs(SystemState.EVIDENCE_DIR)
        
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    try:
        engine = OmniEngine(source=0)
        detector = OmniDetector()
        ui = TacticalUI()
        db = OmniDatabase() 
        voice = OmniVoice() 
    except Exception as e:
        logger.error(f"Failed to initialize system components: {e}")
        return
    
    engine.start()
    voice.start() 
    
    max_wait = 5  
    start_time = time.time()
    while engine.get_frame() is None and (time.time() - start_time) < max_wait:
        time.sleep(0.1)
    
    if engine.get_frame() is None:
        logger.error("Camera failed to provide frames after initialization")
        engine.stop()
        if 'db' in locals(): db.stop()
        if 'voice' in locals(): voice.stop()
        return

    window_name = "OmniVision: Tactical Intelligence"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    prev_time = time.time()
    last_log_state = {} 
    
    # --- TERMAL KONTROL VE FPS LİMİTLEYİCİ AYARLARI ---
    TARGET_FPS = 60
    FRAME_TIME = 1.0 / TARGET_FPS

    try:
        while True:
            # Döngü başlangıç zamanı (Hız Limiti Hesaplaması İçin)
            loop_start = time.time() 
            
            frame = engine.get_frame()
            if frame is None: 
                time.sleep(0.001)
                continue
                
            processed_frame, threats = detector.process(frame)
            
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            final_frame = ui.draw_dashboard(processed_frame, fps)
            
            curr_time = time.time()
            for t in threats:
                obj_id = t['id']
                e_type = t['event_type']
                should_log = False
                
                if obj_id not in last_log_state:
                    should_log = True
                else:
                    time_passed = curr_time - last_log_state[obj_id]['time']
                    type_changed = e_type != last_log_state[obj_id]['type']
                    
                    if type_changed or time_passed >= SystemState.LOG_COOLDOWN:
                        should_log = True
                        
                if should_log:
                    img_path = ""
                    if e_type == "ALARM":
                        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                        img_filename = f"ALARM_obj{obj_id}_{timestamp_str}.jpg"
                        img_path = os.path.join(SystemState.EVIDENCE_DIR, img_filename)
                        
                        threading.Thread(target=save_evidence_async, args=(img_path, final_frame.copy()), daemon=True).start()
                        
                    db.log_threat(
                        object_id=obj_id, label=t['label'], event_type=e_type,
                        duration_sec=t['duration_sec'], confidence=t['confidence'],
                        bbox=t['bbox'], image_path=img_path
                    )
                    last_log_state[obj_id] = {"time": curr_time, "type": e_type}

            tactical_web_dashboard.update_video_frame(final_frame)
            cv2.imshow(window_name, final_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord('d'): SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
            elif key == ord('t'): SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
            elif key == ord('v'): 
                SystemState.VOICE_COMMANDS_ACTIVE = not SystemState.VOICE_COMMANDS_ACTIVE
                if SystemState.VOICE_COMMANDS_ACTIVE:
                    if 'voice' in locals(): voice.play_feedback("listening.mp3")
            elif key == ord('p'): SystemState.SHOW_PERFORMANCE = not SystemState.SHOW_PERFORMANCE
            elif key == ord('a'): 
                SystemState.ALARM_MODE = not SystemState.ALARM_MODE
                print(f"[*] RADAR DURUMU: {'AKTİF' if SystemState.ALARM_MODE else 'PASİF'}")
            elif key == ord('s'): 
                open_target_menu()

            # --- 60 FPS ELEKTRONİK FREN SİSTEMİ ---
            # Eğer döngü 1/60 saniyeden (yaklaşık 16.6ms) daha hızlı bittiyse, arta kalan sürede sistemi dinlendir.
            elapsed_time = time.time() - loop_start
            if elapsed_time < FRAME_TIME:
                time.sleep(FRAME_TIME - elapsed_time)

    except KeyboardInterrupt:
        print("[!] Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        if 'engine' in locals(): engine.stop()
        if 'db' in locals(): db.stop()
        if 'voice' in locals(): voice.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()