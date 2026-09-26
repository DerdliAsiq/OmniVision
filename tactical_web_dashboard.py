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
import time
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from config import SystemState

try:
    from omni_engine import list_local_videos as _list_local_videos, is_youtube_url as _is_youtube_url
except Exception:
    _list_local_videos = None
    _is_youtube_url = None

app = FastAPI(title="OmniVision C2 Merkezi")
security = HTTPBasic()
logger = logging.getLogger("OmniVision")
try:
    DB_NAME = str(SystemState.DB_PATH)
except Exception:
    DB_NAME = str(Path(__file__).parent / "tactical_vision_v2.db")

# [OFANSİF ZİHNİYET] - C2 Paneli ve API'ler için Kimlik Doğrulama Kalkanı
# NOT: Basic Auth + paylasilan oturum nedeniyle tarayici CSRF riski vardir.
# C2 panelini internete ACMAYIN; yalnizca guvenilir LAN/VPN icinde kullanin.
# DELETE /api/wipe gibi yikici islemler icin tarayici onayi (confirm) + auth gerekir.
if SystemState.C2_USERNAME == "admin" and SystemState.C2_PASSWORD == "1234":
    logger.warning("[!] C2 varsayilan kimlik bilgileri (admin/1234) kullaniliyor! .env ile guclu sifre belirleyin.")
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

# C2 uzerinden kaynak degisimi icin engine/detector referansi (main.py set eder).
_engine_ref = None
_detector_ref = None

def set_engine_ref(engine=None, detector=None):
    global _engine_ref, _detector_ref
    _engine_ref = engine
    _detector_ref = detector

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
    last_encode = 0.0
    last_bytes = None
    while True:
        if latest_frame is None:
            await asyncio.sleep(0.1) 
            continue
        with frame_lock:
            frame_to_encode = latest_frame.copy() if latest_frame is not None else None
        if frame_to_encode is None:
            await asyncio.sleep(0.03)
            continue
        # Degismeyen kareyi tekrar encode etme: en fazla ~15fps, degisiklikte aninda.
        now = time.monotonic()
        ret, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if not ret:
            await asyncio.sleep(0.03)
            continue
        frame_bytes = buffer.tobytes()
        # Ayni boyutta ust uste karelerde bant genisligi kazan: 100ms'de bir gonder.
        if last_bytes is not None and len(frame_bytes) == len(last_bytes) and (now - last_encode) < 0.1:
            await asyncio.sleep(0.03)
            continue
        last_bytes = frame_bytes
        last_encode = now
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03)

@app.get("/video_feed")
async def video_feed(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

class CommandData(BaseModel):
    action: str
    payload: list = None
    source: str = None
    amount: float = 10.0

# [SIFIR HATA] Çapraz Platform Ses Motoru Kontrolü
def system_volume_control(action_type):
    os_name = platform.system()
    if os_name == "Windows":
        VK_VOLUME_MUTE = 0xAD
        VK_VOLUME_DOWN = 0xAE
        VK_VOLUME_UP = 0xAF
        try:
            user32 = ctypes.windll.user32
            def _tap(vk):
                # Bas + birak (KEYEVENTF_KEYUP) cifti gonder, tusa basili kalmasin.
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 2, 0)
            if action_type == "up":
                _tap(VK_VOLUME_UP)
            elif action_type == "down":
                _tap(VK_VOLUME_DOWN)
            elif action_type == "mute":
                _tap(VK_VOLUME_MUTE)
            elif action_type == "max":
                _tap(VK_VOLUME_MUTE)  # Olasi mute durumunu kaldir
                for _ in range(20):  # %100'e yaklastir (50x flood yerine sinirli)
                    _tap(VK_VOLUME_UP)
        except Exception as e:
            logger.warning(f"Windows ses kontrol hatasi: {e}")
    else:
        # Linux (Arch/Garuda) Fallback - kabuk kullanmadan, liste arguman.
        def _run(*args):
            try:
                subprocess.Popen(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.warning(f"pactl hatasi: {e}")
        if action_type == "up":
            _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%")
        elif action_type == "down":
            _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%")
        elif action_type == "mute":
            _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle")
        elif action_type == "max":
            _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "0")
            _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%")

@app.post("/api/command")
async def execute_command(cmd: CommandData, credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    action = cmd.action
    allowed = {"toggle_alarm", "toggle_hud", "toggle_track", "set_targets", "set_source",
               "play_pause", "toggle_pause", "seek_fwd", "seek_back", "seek",
               "vol_up", "vol_down", "vol_mute", "vol_max"}
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen komut: {action}")
    if action == "toggle_alarm": SystemState.ALARM_MODE = not SystemState.ALARM_MODE
    elif action == "toggle_hud": SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
    elif action == "toggle_track": SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
    elif action == "set_targets" and cmd.payload is not None:
        try:
            ids = [int(i) for i in cmd.payload]
        except Exception:
            raise HTTPException(status_code=400, detail="payload int liste olmali")
        if not SystemState.MODEL_CLASSES:
            raise HTTPException(status_code=409, detail="Model siniflari henuz hazir degil")
        unknown = [i for i in ids if i not in SystemState.MODEL_CLASSES]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Bilinmeyen sinif ID: {unknown[:10]}")
        SystemState.ACTIVE_TARGET_IDS = ids
        SystemState.ACTIVE_TARGET_NAMES = [SystemState.MODEL_CLASSES[i].upper() for i in ids]
    elif action == "set_source" and cmd.source:
        if _engine_ref is None:
            raise HTTPException(status_code=409, detail="Goruntu motoru henuz bagli degil")
        src = cmd.source.strip()
        # Web panel sadece dosya adi gonderirse Video_Analiz icinde coz.
        try:
            _is_yt = bool(_is_youtube_url(src)) if _is_youtube_url else ("youtube.com/" in src or "youtu.be/" in src)
        except Exception:
            _is_yt = False
        if src and "/" not in src and "\\" not in src and not src.isdigit() \
           and "://" not in src and not _is_yt:
            cand = os.path.join(SystemState.VIDEO_DIR, src)
            if os.path.isfile(cand):
                src = cand
        if hasattr(_engine_ref, "request_switch"):
            # Async: event-loop bloklanmaz, eski yayin akmaya devam eder.
            def _done(ok, payload):
                if ok and _detector_ref is not None and hasattr(_detector_ref, "reset_history"):
                    try:
                        _detector_ref.reset_history()
                    except Exception:
                        pass
            try:
                _engine_ref.request_switch(src, on_done=_done)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
            return {"status": "connecting", "action": action, "source": src,
                    "label": _engine_ref.get_source_label()}
        try:
            stype = _engine_ref.switch_source(src)
            if _detector_ref is not None and hasattr(_detector_ref, "reset_history"):
                try:
                    _detector_ref.reset_history()
                except Exception:
                    pass
            return {"status": "success", "action": action, "source_type": stype,
                    "label": _engine_ref.get_source_label()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif action in ["play_pause", "toggle_pause"]:
        if _engine_ref is None:
            raise HTTPException(status_code=409, detail="Goruntu motoru henuz bagli degil")
        paused = _engine_ref.toggle_pause()
        return {"status": "success", "action": action, "paused": bool(_engine_ref.is_paused())}
    elif action in ["seek_fwd", "seek_back", "seek"]:
        if _engine_ref is None:
            raise HTTPException(status_code=409, detail="Goruntu motoru henuz bagli degil")
        try:
            amt = float(cmd.amount if cmd.amount else 10.0)
        except Exception:
            amt = 10.0
        if action == "seek_back":
            amt = -abs(amt)
        elif action == "seek_fwd":
            amt = abs(amt)
        ok = _engine_ref.seek(amt)
        if not ok:
            raise HTTPException(status_code=400, detail="Bu kaynakta seek yok (canli yayin).")
        return {"status": "success", "action": action, "amount": amt}
    elif action in ["vol_up", "vol_down", "vol_mute", "vol_max"]:
        system_volume_control(action.replace("vol_", ""))
    return {"status": "success", "action": action}

@app.get("/api/media")
async def list_media(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    vdir = SystemState.VIDEO_DIR
    try:
        _os.makedirs(vdir, exist_ok=True)
        if _list_local_videos is not None:
            files = [_os.path.basename(p) for p in _list_local_videos()]
        else:
            files = []
    except Exception as e:
        logger.warning(f"Medya listeleme hatasi: {e}")
        files = []
    info = {}
    try:
        if _engine_ref is not None and hasattr(_engine_ref, "get_playback_info"):
            info = _engine_ref.get_playback_info()
    except Exception:
        info = {}
    return {"video_dir": vdir,
            "videos": files,
            "current_source": getattr(SystemState, "CURRENT_SOURCE", "0"),
            "current_label": getattr(SystemState, "CURRENT_SOURCE_LABEL", ""),
            "source_type": getattr(SystemState, "SOURCE_TYPE", "camera"),
            "paused": info.get("paused", bool(getattr(SystemState, "PLAY_PAUSED", False))),
            "seekable": info.get("seekable", bool(getattr(SystemState, "SEEKABLE", False))),
            "pos": info.get("pos", float(getattr(SystemState, "PLAY_POS_SEC", 0.0))),
            "dur": info.get("dur", float(getattr(SystemState, "PLAY_DUR_SEC", 0.0))),
            "connecting": info.get("connecting", bool(getattr(SystemState, "CONNECTING", False))),
            "pending": info.get("pending", str(getattr(SystemState, "CONNECTING_LABEL", ""))),
            "connect_error": info.get("connect_error", str(getattr(SystemState, "CONNECT_ERROR", "")))}

@app.get("/api/classes")
async def get_model_classes(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return SystemState.MODEL_CLASSES

@app.get("/api/logs")
async def get_logs(q: str = "", limit: int = 100, offset: int = 0,
                   credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    if not os.path.exists(DB_NAME): return []
    limit = max(1, min(int(limit or 100), 500))
    offset = max(0, int(offset or 0))
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if q:
            query = f"%{q}%"
            cursor.execute("SELECT * FROM threat_logs WHERE label LIKE ? OR event_type LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?", (query, query, limit, offset))
        else:
            cursor.execute("SELECT * FROM threat_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = [dict(r) for r in cursor.fetchall()]
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
        try:
            cursor.execute("VACUUM")
        except Exception:
            pass
        conn.close()
        if os.path.exists(SystemState.EVIDENCE_DIR):
            for f in os.listdir(SystemState.EVIDENCE_DIR):
                # Sadece kanit JPG'leri sil, .gitkeep/README gibi dosyalara dokunma.
                if not f.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                if not (f.startswith("ALARM_") or f.startswith("_yt_")) and f.lower().endswith((".jpg", ".jpeg", ".png")):
                    # Kanit adlandirmasi disinda dosya varsa yine silme disinda tutma:
                    # sadece ALARM_/kanit pattern'i silinir.
                    if not f.startswith("ALARM_"):
                        continue
                try:
                    os.remove(os.path.join(SystemState.EVIDENCE_DIR, f))
                except Exception as e:
                    logger.warning(f"Kanıt dosyası silme hatası: {e}")
    return {"status": "cleared"}

_dashboard_html_cache = {"mtime": None, "content": None}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    html_path = Path(__file__).parent / "templates" / "index.html"
    try:
        mtime = html_path.stat().st_mtime
    except Exception:
        mtime = None
    if _dashboard_html_cache["content"] is None or _dashboard_html_cache["mtime"] != mtime:
        _dashboard_html_cache["content"] = html_path.read_text(encoding="utf-8")
        _dashboard_html_cache["mtime"] = mtime
    return _dashboard_html_cache["content"]