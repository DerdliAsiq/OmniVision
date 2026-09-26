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
from media_menu import open_media_menu
import tactical_web_dashboard
import tk_policy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

DEBUG_FONT = None

def run_web_server():
    # Varsayilan kimlik bilgileriyle LAN'a acilma: acik onay (C2_ALLOW_LAN=1) sart.
    use_default_creds = (SystemState.C2_USERNAME == "admin" and SystemState.C2_PASSWORD == "1234")
    allow_lan = bool(getattr(SystemState, "C2_ALLOW_LAN", False))
    host = "0.0.0.0" if (allow_lan or not use_default_creds) else getattr(SystemState, "C2_HOST_FALLBACK", "127.0.0.1")
    if use_default_creds and host == "0.0.0.0":
        logger.warning("[!] Varsayilan C2 kimlik bilgileriyle LAN'a aciliyor! .env ile guclu sifre belirleyin.")
    try:
        port = int(getattr(SystemState, "C2_PORT", 8000) or 8000)
    except Exception:
        port = 8000
    logger.info(f"[+] C2 Web Sunucusu Başlatılıyor: http://{host}:{port}")
    uvicorn.run(tactical_web_dashboard.app, host=host, port=port, log_level="warning")

# OPTİMİZASYON: Görüntü Kaydetme İşlemini Ana Döngüden Koparan Gölge Fonksiyon
def save_evidence_async(img_path, frame_copy):
    try:
        d = os.path.dirname(img_path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        cv2.imwrite(img_path, frame_copy)
    except Exception as e:
        logger.warning(f"Kanit yazilamadi ({img_path}): {e}")

def main():
    print(f"[+] OmniVision V{SystemState.VERSION} Başlatılıyor (Voice C2 Devrede)...")
    
    if not os.path.exists(SystemState.EVIDENCE_DIR):
        os.makedirs(SystemState.EVIDENCE_DIR)
    if not os.path.exists(SystemState.VIDEO_DIR):
        os.makedirs(SystemState.VIDEO_DIR)
        
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    try:
        try:
            engine = OmniEngine(source=0)
        except Exception as cam_err:
            # Kamera yoksa Video_Analiz'deki ilk videoya dus (saha/offline modu).
            logger.warning(f"Kamera acilamadi ({cam_err}). Video_Analiz taraniyor...")
            try:
                from omni_engine import list_local_videos
                vids = list_local_videos()
            except Exception:
                vids = []
            if not vids:
                raise cam_err
            engine = OmniEngine(source=vids[0])
        detector = OmniDetector()
        ui = TacticalUI()
        db = OmniDatabase() 
        voice = OmniVoice() 
        lidar = OmniLidar()
        try:
            tactical_web_dashboard.set_engine_ref(engine, detector)
        except Exception:
            pass
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
    headless = os.getenv("HEADLESS", "0") == "1" or os.getenv("OMNIVISION_HEADLESS", "0") == "1"
    if not headless:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        except Exception as e:
            logger.warning(f"Fullscreen acilamadi, headless moda geciliyor: {e}")
            headless = True

    prev_time = time.time()
    last_log_state = {}
    LOG_STATE_TTL = 600.0
    LOG_STATE_MAX = 500
    frame_times = []
    last_final = None
    
    try:
        while True:
            loop_start = time.perf_counter()

            # Motor reconnect limitini asip durduysa hayalet kareyle donme, cik.
            try:
                engine_alive = bool(getattr(engine, "is_running", True))
            except Exception:
                engine_alive = True
            if not engine_alive and engine.get_frame() is None:
                logger.error("[X] Goruntu motoru durdu (reconnect limiti). Cikis yapiliyor.")
                break
            
            frame = engine.get_frame()
            # Motor durdu + frame yoksa ayni sekilde cik (sonsuz dongu olmasin).
            if frame is None and not engine_alive:
                logger.error("[X] Goruntu motoru durdu, gosterilecek kare yok.")
                break
            if frame is None:
                # Gecis/buffer aninda CPU'yu yakma; son iyi kareyi baglaniyor
                # overlay'iyle goster, hic kare yoksa kisa bekle.
                connecting = False
                try:
                    connecting = bool(engine.is_connecting())
                except Exception:
                    pass
                if last_final is not None and connecting:
                    try:
                        show = last_final.copy()
                        msg = "BAGLANIYOR..."
                        try:
                            pend = str(getattr(engine, "_pending_label", "") or "")[:40]
                            if pend:
                                msg = f"BAGLANIYOR: {pend}"
                        except Exception:
                            pass
                        cv2.putText(show, msg, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
                        tactical_web_dashboard.update_video_frame(show)
                        if not headless:
                            cv2.imshow(window_name, show)
                    except Exception:
                        pass
                    if not headless:
                        cv2.waitKey(30)
                    else:
                        time.sleep(0.03)
                else:
                    time.sleep(0.03)
                    if not headless:
                        cv2.waitKey(1)
                continue
                
            t0 = time.perf_counter()
            processed_frame, threats = detector.process(frame)
            inference_ms = (time.perf_counter() - t0) * 1000
            
            new_time = time.time()
            fps = 1 / (new_time - prev_time) if (new_time - prev_time) > 0 else 0
            prev_time = new_time
            
            final_frame = ui.draw_dashboard(processed_frame, fps, engine, inference_ms)
            
            curr_time = time.time()
            # TTL evict: uzun calismada last_log_state sissin diye periyodik temizle.
            if len(last_log_state) > LOG_STATE_MAX:
                try:
                    stale = [k for k, v in last_log_state.items() if (curr_time - v.get("time", 0)) > LOG_STATE_TTL]
                    for k in stale:
                        last_log_state.pop(k, None)
                    # Hala buyukse en eskileri at.
                    while len(last_log_state) > LOG_STATE_MAX:
                        oldest = min(last_log_state, key=lambda k: last_log_state[k].get("time", 0))
                        last_log_state.pop(oldest, None)
                except Exception:
                    pass
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
                        # Queue doluysa orphan JPG birakma: once DB'ye sor, kabul edilirse yaz.
                        accepted = db.log_threat(
                            object_id=obj_id, label=t['label'], event_type=e_type,
                            duration_sec=t['duration_sec'], confidence=t['confidence'],
                            bbox=t['bbox'], image_path=img_path
                        )
                        if accepted:
                            try:
                                threading.Thread(target=save_evidence_async, args=(img_path, final_frame.copy()), daemon=True).start()
                            except Exception:
                                pass
                        else:
                            img_path = ""
                        last_log_state[obj_id] = {"time": curr_time, "type": e_type}
                    else:
                        db.log_threat(
                            object_id=obj_id, label=t['label'], event_type=e_type,
                            duration_sec=t['duration_sec'], confidence=t['confidence'],
                            bbox=t['bbox'], image_path=img_path
                        )
                        last_log_state[obj_id] = {"time": curr_time, "type": e_type}

            tactical_web_dashboard.update_video_frame(final_frame)
            if not headless:
                cv2.imshow(window_name, final_frame)
            try:
                last_final = final_frame
            except Exception:
                pass
            
            if headless:
                time.sleep(0.01)
                key = 255  # headless'ta klavye yok
            else:
                key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord('d'): SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
            elif key == ord('t'): SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
            elif key == ord('v'): 
                SystemState.VOICE_COMMANDS_ACTIVE = not SystemState.VOICE_COMMANDS_ACTIVE
                if SystemState.VOICE_COMMANDS_ACTIVE:
                    if 'voice' in locals() and voice.is_ready():
                        voice.play_feedback("listening.mp3")
                    else:
                        print("[X] Sesli komut motoru hazır değil (PyAudio/Whisper modelini kontrol edin).")
                        if 'voice' in locals(): voice.play_feedback("error.mp3")
            elif key == ord('p'): SystemState.SHOW_PERFORMANCE = not SystemState.SHOW_PERFORMANCE
            elif key == ord('a'): 
                SystemState.ALARM_MODE = not SystemState.ALARM_MODE
                print(f"[*] RADAR DURUMU: {'AKTİF' if SystemState.ALARM_MODE else 'PASİF'}")
            elif key == ord('s'):
                # Tk servis thread'ine kuyruklanir, video dongusu bloklanmaz.
                try:
                    open_target_menu()
                except Exception as e:
                    print(f"[X] Hedef menus acilamadi: {e}")
            elif key == ord('c') or key == ord('C'):
                # [C] Goruntu kaynagi menusu: kamera / Video_Analiz / RTSP / YouTube.
                try:
                    open_media_menu(engine, detector)
                except Exception as e:
                    print(f"[X] Medya menus acilamadi: {e}")
            elif key == ord(' '):
                # Space: duraklat/devam (video + canli).
                try:
                    paused = engine.toggle_pause()
                    print(f"[*] OYNATMA: {'DURAKLATILDI' if engine.is_paused() else 'DEVAM'}")
                except Exception as e:
                    print(f"[X] Pause hatasi: {e}")
            elif key == ord(','):
                # , : -5 sn (sadece seekable: video / indirilmis YT-VOD).
                if not engine.seek(-5):
                    print("[!] Geri sarma bu kaynakta yok (canli).")
            elif key == ord('.'):
                # . : +5 sn (sadece seekable).
                if not engine.seek(5):
                    print("[!] Ileri sarma bu kaynakta yok (canli).")
            elif key == ord('z'):
                SystemState.POLYGON_ZONES_ACTIVE = not SystemState.POLYGON_ZONES_ACTIVE
                print(f"[*] SANAL ÇİT: {'AKTİF' if SystemState.POLYGON_ZONES_ACTIVE else 'PASİF'}")
            elif key == ord('l'):
                SystemState.LIDAR_ACTIVE = not SystemState.LIDAR_ACTIVE
                print(f"[*] LiDAR/SONAR: {'AKTİF' if SystemState.LIDAR_ACTIVE else 'PASİF'}")
            elif key == ord('h') or key == ord('H'):
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
        # Tk servis thread'ini once graceful kapat (daemon abort -> Tcl_AsyncDelete olmasin).
        try:
            tk_policy.shutdown(timeout=3.0)
        except Exception:
            pass
        if 'engine' in locals(): engine.stop()
        if 'db' in locals(): db.stop()
        if 'voice' in locals(): voice.stop()
        if 'lidar' in locals(): lidar.stop()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

if __name__ == "__main__":
    main()