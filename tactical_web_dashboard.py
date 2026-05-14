import sqlite3
import cv2
import threading
import os
from pathlib import Path
import asyncio
import subprocess
import io
import platform
import ctypes
import secrets
import logging
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from config import SystemState

app = FastAPI(title="OmniVision C2 Merkezi")
security = HTTPBasic()
logger = logging.getLogger("OmniVision")
DB_NAME = "tactical_vision_v2.db"

# [OFANSİF ZİHNİYET] - C2 Paneli ve API'ler için Kimlik Doğrulama Kalkanı
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, SystemState.C2_USERNAME)
    is_pass_ok = secrets.compare_digest(credentials.password, SystemState.C2_PASSWORD)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetkisiz Erişim - İntruder Tespit Edildi",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Kanıt klasörünü oluştur ve statik olarak mount et
if not os.path.exists(SystemState.EVIDENCE_DIR):
    os.makedirs(SystemState.EVIDENCE_DIR)
# Dizin yolunu çapraz platform için güvenli hale getir
app.mount(f"/{os.path.basename(SystemState.EVIDENCE_DIR)}", StaticFiles(directory=SystemState.EVIDENCE_DIR), name="evidence")

latest_frame = None
frame_lock = threading.Lock()

def update_video_frame(frame):
    global latest_frame
    try:
        # Web yayını 480p Downscale (Ağ bant genişliği optimizasyonu)
        h, w = frame.shape[:2]
        scale = 480 / h
        new_w = int(w * scale)
        small_frame = cv2.resize(frame, (new_w, 480))
        with frame_lock:
            latest_frame = small_frame
    except Exception as e:
        logger.warning(f"Video frame güncelleme hatası: {e}")

async def video_generator():
    global latest_frame
    while True:
        if latest_frame is None:
            await asyncio.sleep(0.1) 
            continue
        with frame_lock:
            frame_to_encode = latest_frame
        ret, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if not ret:
            await asyncio.sleep(0.03)
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03)

@app.get("/video_feed")
async def video_feed(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

class CommandData(BaseModel):
    action: str
    payload: list = None

# [SIFIR HATA] Çapraz Platform Ses Motoru Kontrolü
def system_volume_control(action_type):
    os_name = platform.system()
    if os_name == "Windows":
        VK_VOLUME_MUTE = 0xAD
        VK_VOLUME_DOWN = 0xAE
        VK_VOLUME_UP = 0xAF
        if action_type == "up":
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
        elif action_type == "down":
            ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
        elif action_type == "mute":
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        elif action_type == "max":
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0) # Olası Mute durumunu kaldır
            for _ in range(50): # %100'e zorlamak için seri tetikleme
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
    else:
        # Linux (Arch/Garuda) Fallback
        if action_type == "up":
            subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ +10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action_type == "down":
            subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ -10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action_type == "mute":
            subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ toggle", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action_type == "max":
            subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ 0", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ 100%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.post("/api/command")
async def execute_command(cmd: CommandData, credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    action = cmd.action
    if action == "toggle_alarm": SystemState.ALARM_MODE = not SystemState.ALARM_MODE
    elif action == "toggle_hud": SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
    elif action == "toggle_track": SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
    elif action == "set_targets" and cmd.payload is not None:
        SystemState.ACTIVE_TARGET_IDS = cmd.payload
        SystemState.ACTIVE_TARGET_NAMES = [SystemState.MODEL_CLASSES[i].upper() for i in cmd.payload]
    elif action in ["vol_up", "vol_down", "vol_mute", "vol_max"]:
        system_volume_control(action.replace("vol_", ""))
    return {"status": "success", "action": action}

@app.get("/api/classes")
async def get_model_classes(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return SystemState.MODEL_CLASSES

@app.get("/api/logs")
async def get_logs(q: str = "", credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    if not os.path.exists(DB_NAME): return []
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        if q:
            query = f"%{q}%"
            cursor.execute("SELECT * FROM threat_logs WHERE label LIKE ? OR event_type LIKE ? ORDER BY id DESC LIMIT 100", (query, query))
        else:
            cursor.execute("SELECT * FROM threat_logs ORDER BY id DESC LIMIT 100")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"Log sorgulama hatası: {e}")
        return []

@app.get("/api/summary")
async def get_summary(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    if not os.path.exists(DB_NAME): return {"total": 0, "anomalies": 0, "alarms": 0}
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT object_id) FROM threat_logs WHERE timestamp >= date('now', '-1 day')")
        total = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(DISTINCT object_id) FROM threat_logs WHERE event_type='ANOMALY' AND timestamp >= date('now', '-1 day')")
        anomalies = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(DISTINCT object_id) FROM threat_logs WHERE event_type='ALARM' AND timestamp >= date('now', '-1 day')")
        alarms = cursor.fetchone()[0] or 0
        conn.close()
        return {"total": total, "anomalies": anomalies, "alarms": alarms}
    except Exception as e:
        logger.warning(f"Özet sorgulama hatası: {e}")
        return {"total": 0, "anomalies": 0, "alarms": 0}

@app.get("/api/export_csv")
async def export_csv(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    if not os.path.exists(DB_NAME): return Response(content="No data", media_type="text/plain")
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, object_id, label, event_type, duration_sec, confidence, x_center, y_center FROM threat_logs ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        csv_content = "ID,TARIH,NESNE_ID,SINIF,OLAY_TURU,SURE_SN,GUVEN_ORANI,X,Y\n"
        for row in rows:
            csv_content += f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]:.2f},{row[7]},{row[8]}\n"
        return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=omnivision_istihbarat_raporu.csv"})
    except Exception as e:
        logger.warning(f"CSV export hatası: {e}")
        return Response(content="Error generating CSV", media_type="text/plain")

@app.delete("/api/wipe")
async def wipe_database(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    if os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM threat_logs")
        conn.commit()
        conn.close()
        if os.path.exists(SystemState.EVIDENCE_DIR):
            for f in os.listdir(SystemState.EVIDENCE_DIR):
                try:
                    os.remove(os.path.join(SystemState.EVIDENCE_DIR, f))
                except Exception as e:
                    logger.warning(f"Kanıt dosyası silme hatası: {e}")
    return {"status": "cleared"}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")