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
from omni_lidar import OmniLidar
from config import SystemState
from target_menu import open_target_menu
import tactical_web_dashboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

DEBUG_FONT = None

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
        lidar = OmniLidar()
    except Exception as e:
        logger.error(f"Failed to initialize system components: {e}")
        return
    
    engine.start()
    voice.start()
    lidar.start()
    
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
    frame_times = []
    
    try:
        while True:
            loop_start = time.perf_counter()
            
            frame = engine.get_frame()
            if frame is None: 
                continue
                
            t0 = time.perf_counter()
            processed_frame, threats = detector.process(frame)
            inference_ms = (time.perf_counter() - t0) * 1000
            
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            final_frame = ui.draw_dashboard(processed_frame, fps, engine, inference_ms)
            
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
            elif key == ord('z'):
                SystemState.POLYGON_ZONES_ACTIVE = not SystemState.POLYGON_ZONES_ACTIVE
                print(f"[*] SANAL ÇİT: {'AKTİF' if SystemState.POLYGON_ZONES_ACTIVE else 'PASİF'}")
            elif key == ord('l'):
                SystemState.LIDAR_ACTIVE = not SystemState.LIDAR_ACTIVE
                print(f"[*] LiDAR/SONAR: {'AKTİF' if SystemState.LIDAR_ACTIVE else 'PASİF'}")
            elif key == 0x70:
                SystemState.DEBUG_MODE = not SystemState.DEBUG_MODE
                print(f"[*] DEBUG MOD: {'AKTİF' if SystemState.DEBUG_MODE else 'PASİF'}")

            elapsed_ms = (time.perf_counter() - loop_start) * 1000
            frame_times.append(elapsed_ms)
            if len(frame_times) > 30:
                frame_times.pop(0)
            avg_ms = sum(frame_times) / len(frame_times)
            if avg_ms < 20:
                remaining = 20 - avg_ms
                if remaining > 1 and remaining < 50:
                    time.sleep(remaining / 1000.0)

    except KeyboardInterrupt:
        print("[!] Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        if 'engine' in locals(): engine.stop()
        if 'db' in locals(): db.stop()
        if 'voice' in locals(): voice.stop()
        if 'lidar' in locals(): lidar.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()