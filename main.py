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

def main():
    print("[+] OmniVision V1.3 Başlatılıyor (Voice C2 Devrede)...")
    
    # Kanıt klasörünün varlığını güvenceye al
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

    try:
        while True:
            frame = engine.get_frame()
            if frame is None: continue
                
            processed_frame, threats = detector.process(frame)
            
            # 1. Önce FPS'i hesapla ve HUD'u (Arayüzü) çiz!
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            final_frame = ui.draw_dashboard(processed_frame, fps)
            
            # ==========================================
            # 🖥️ TAKTİKSEL KONTROLLER (PREDATOR HUD)
            # ==========================================
            if SystemState.SHOW_DASHBOARD:
                h, w = final_frame.shape[:2]
                
                overlay = final_frame.copy()
                cv2.rectangle(overlay, (10, h - 110), (350, h - 10), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, final_frame, 0.4, 0, final_frame)
                
                cv2.rectangle(final_frame, (10, h - 110), (350, h - 10), (0, 255, 0), 1)
                cv2.putText(final_frame, "TAKTIKSEL KONTROLLER", (20, h - 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                trk_color = (0, 255, 0) if SystemState.TRACKING_ACTIVE else (0, 0, 255)
                trk_text = "AKTIF" if SystemState.TRACKING_ACTIVE else "PASIF"
                cv2.putText(final_frame, f"[T] Hedef Takibi : {trk_text}", (20, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, trk_color, 2)
                
                voc_color = (0, 255, 0) if SystemState.VOICE_COMMANDS_ACTIVE else (0, 0, 255)
                voc_text = "DINLIYOR" if SystemState.VOICE_COMMANDS_ACTIVE else "KAPALI"
                cv2.putText(final_frame, f"[V] Ses Karargahi: {voc_text}", (20, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, voc_color, 2)

            # 2. Şimdi (Tüm ekran çizimleri bittikten sonra) Tehditleri Logla ve FOTO ÇEK
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
                    # SADECE "ALARM" VERİLDİĞİNDE FOTOĞRAF ÇEK
                    if e_type == "ALARM":
                        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                        img_filename = f"ALARM_obj{obj_id}_{timestamp_str}.jpg"
                        img_path = os.path.join(SystemState.EVIDENCE_DIR, img_filename)
                        cv2.imwrite(img_path, final_frame)
                        
                    db.log_threat(
                        object_id=obj_id,
                        label=t['label'],
                        event_type=e_type,
                        duration_sec=t['duration_sec'],
                        confidence=t['confidence'],
                        bbox=t['bbox'],
                        image_path=img_path
                    )
                    last_log_state[obj_id] = {"time": curr_time, "type": e_type}

            # Görüntüyü Web Sunucusuna ve Ekrana Aktar
            tactical_web_dashboard.update_video_frame(final_frame)
            cv2.imshow(window_name, final_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): 
                break
            elif key == ord('d'): 
                SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
            elif key == ord('t'): 
                SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
            elif key == ord('v'): 
                SystemState.VOICE_COMMANDS_ACTIVE = not SystemState.VOICE_COMMANDS_ACTIVE
                if SystemState.VOICE_COMMANDS_ACTIVE:
                    if 'voice' in locals(): voice.play_feedback("listening.mp3")
            elif key == ord('p'): 
                SystemState.SHOW_PERFORMANCE = not SystemState.SHOW_PERFORMANCE
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
        if 'voice' in locals(): voice.stop()
        cv2.destroyAllWindows()
        print("[+] Sistem Güvenli Şekilde Kapatıldı.")

if __name__ == "__main__":
    main()