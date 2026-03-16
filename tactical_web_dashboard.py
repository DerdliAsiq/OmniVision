import sqlite3
import cv2
import threading
import os
import asyncio
import subprocess
import io
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from config import SystemState

app = FastAPI(title="OmniVision C2 Merkezi")
DB_NAME = "tactical_vision_v2.db"

if not os.path.exists(SystemState.EVIDENCE_DIR):
    os.makedirs(SystemState.EVIDENCE_DIR)
app.mount(f"/{SystemState.EVIDENCE_DIR}", StaticFiles(directory=SystemState.EVIDENCE_DIR), name="evidence")

latest_frame = None
frame_lock = threading.Lock()

def update_video_frame(frame):
    global latest_frame
    try:
        # OPTİMİZASYON: Web yayını 480p'ye Downscale edilir.
        h, w = frame.shape[:2]
        scale = 480 / h
        new_w = int(w * scale)
        small_frame = cv2.resize(frame, (new_w, 480))
        with frame_lock:
            latest_frame = small_frame
    except Exception:
        pass

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
async def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

class CommandData(BaseModel):
    action: str
    payload: list = None

@app.post("/api/command")
async def execute_command(cmd: CommandData):
    action = cmd.action
    if action == "toggle_alarm": SystemState.ALARM_MODE = not SystemState.ALARM_MODE
    elif action == "toggle_hud": SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
    elif action == "toggle_track": SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
    elif action == "set_targets" and cmd.payload is not None:
        SystemState.ACTIVE_TARGET_IDS = cmd.payload
        SystemState.ACTIVE_TARGET_NAMES = [SystemState.MODEL_CLASSES[i].upper() for i in cmd.payload]
    elif action == "vol_up": subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ +10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_down": subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ -10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_mute": subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ toggle", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_max":
        subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ 0", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ 100%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "success", "action": action}

@app.get("/api/classes")
async def get_model_classes():
    return SystemState.MODEL_CLASSES

@app.get("/api/logs")
async def get_logs(q: str = ""):
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
    except Exception as e: return []

@app.get("/api/summary")
async def get_summary():
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
    except Exception: return {"total": 0, "anomalies": 0, "alarms": 0}

@app.get("/api/export_csv")
async def export_csv():
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
    except Exception as e: return Response(content="Error generating CSV", media_type="text/plain")

@app.delete("/api/wipe")
async def wipe_database():
    if os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM threat_logs")
        conn.commit()
        conn.close()
        
        if os.path.exists(SystemState.EVIDENCE_DIR):
            for f in os.listdir(SystemState.EVIDENCE_DIR):
                os.remove(os.path.join(SystemState.EVIDENCE_DIR, f))
    return {"status": "cleared"}

# --- YENİ NESİL FULLY-RESPONSIVE SİBER-KARARGAH TASARIMI ---
html_content = """
<!DOCTYPE html>
<html lang="tr" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>OmniVision | Tactical Command</title>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        :root[data-theme="dark"] {
            --bg-void: #050608;
            --panel-bg: rgba(10, 14, 23, 0.75);
            --panel-border: rgba(0, 229, 255, 0.2);
            --text-main: #e2e8f0;
            --text-muted: #64748b;
            --accent-cyan: #00e5ff;
            --accent-cyan-glow: rgba(0, 229, 255, 0.5);
            --danger: #ff2a2a;
            --danger-glow: rgba(255, 42, 42, 0.5);
            --warning: #ffb700;
            --success: #00ff66;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.5); }
        ::-webkit-scrollbar-thumb { background: var(--accent-cyan); border-radius: 3px; }

        body { 
            background-color: var(--bg-void); 
            background-image: radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.08) 0%, transparent 60%);
            color: var(--text-main); 
            font-family: 'Rajdhani', sans-serif; 
            margin: 0; padding: 15px; 
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Başlık Sistemi */
        .header { 
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--panel-border); 
            padding-bottom: 15px; margin-bottom: 20px; 
        }
        .header h2 { 
            margin: 0; font-size: 1.8rem; letter-spacing: 2px; color: #fff; 
            text-shadow: 0 0 12px var(--accent-cyan-glow);
            display: flex; align-items: center;
        }
        
        .live-dot { 
            width: 10px; height: 10px; background: var(--danger); 
            border-radius: 50%; display: inline-block; 
            box-shadow: 0 0 10px var(--danger);
            animation: blink 1.5s infinite; margin-right: 15px; 
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }

        /* Taktiksel Sekmeler */
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; overflow-x: auto; padding-bottom: 5px; }
        .tab-btn { 
            background: rgba(0, 0, 0, 0.6); color: var(--text-muted); 
            border: 1px solid var(--panel-border); border-radius: 4px;
            padding: 12px 20px; cursor: pointer; font-family: 'Share Tech Mono', monospace; 
            font-size: 14px; letter-spacing: 1px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            white-space: nowrap; flex: 1; text-align: center;
        }
        .tab-btn:hover { border-color: var(--accent-cyan); color: #fff; }
        .tab-btn.active { 
            background: rgba(0, 229, 255, 0.15); color: var(--accent-cyan); 
            border-color: var(--accent-cyan); box-shadow: 0 0 15px var(--accent-cyan-glow); 
        }
        
        .tab-content { display: none; animation: fadeIn 0.3s ease-out; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* Akıllı Izgara (Mobil Uyumluluk İçin) */
        .main-layout { display: flex; flex-direction: row; gap: 20px; }
        .video-column { flex: 2.5; }
        .controls-column { flex: 1; min-width: 320px; display: flex; flex-direction: column; gap: 20px; }

        /* Predator Vizör Çerçevesi */
        .video-wrapper {
            position: relative; background: #000; padding: 2px;
            border-radius: 8px; border: 1px solid var(--panel-border);
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            overflow: hidden;
        }
        .video-wrapper::before, .video-wrapper::after {
            content: ''; position: absolute; width: 40px; height: 40px; 
            border: 3px solid var(--accent-cyan); pointer-events: none; z-index: 10;
        }
        .video-wrapper::before { top: 0; left: 0; border-right: none; border-bottom: none; border-radius: 8px 0 0 0; }
        .video-wrapper::after { bottom: 0; right: 0; border-left: none; border-top: none; border-radius: 0 0 8px 0; }
        .video-feed { width: 100%; height: auto; display: block; border-radius: 6px; }

        /* Glassmorphism Paneller */
        .glass-panel { 
            background: var(--panel-bg); 
            backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
            border: 1px solid var(--panel-border); 
            border-radius: 8px; padding: 20px; 
            box-shadow: inset 0 0 20px rgba(0, 229, 255, 0.05), 0 4px 15px rgba(0,0,0,0.4);
        }
        .glass-panel h3 { 
            margin-top: 0; color: var(--accent-cyan); font-family: 'Share Tech Mono', monospace; 
            font-size: 14px; border-bottom: 1px solid rgba(0, 229, 255, 0.3); padding-bottom: 8px; margin-bottom: 15px;
            text-transform: uppercase; letter-spacing: 2px; display: flex; align-items: center; gap: 8px;
        }

        /* YENİ NESİL SİBER BUTONLAR (Hover & Active) */
        button.cmd-btn { 
            width: 100%; padding: 15px; margin-bottom: 12px; 
            background: rgba(0, 0, 0, 0.6); color: var(--accent-cyan); 
            border: 1px solid var(--accent-cyan); border-radius: 6px;
            cursor: pointer; font-family: 'Rajdhani', sans-serif; font-size: 16px; font-weight: 700; letter-spacing: 1.5px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); position: relative; overflow: hidden;
            text-transform: uppercase;
        }
        button.cmd-btn:hover { 
            background: rgba(0, 229, 255, 0.2); 
            color: #fff; box-shadow: 0 0 20px var(--accent-cyan-glow); 
        }
        button.cmd-btn:active { transform: scale(0.97); } /* Dokunma/Basma Hissi */

        button.cmd-btn.alarm { border-color: var(--danger); color: var(--danger); }
        button.cmd-btn.alarm:hover { background: rgba(255, 42, 42, 0.2); color: #fff; box-shadow: 0 0 20px var(--danger-glow); }
        
        button.cmd-btn.override { background: rgba(255, 42, 42, 0.15); border-color: var(--danger); color: #fff; }
        button.cmd-btn.override:hover { background: var(--danger); box-shadow: 0 0 25px var(--danger-glow); }
        
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        
        select.target-select { 
            width: 100%; height: 160px; background: rgba(0, 0, 0, 0.8); color: var(--accent-cyan); 
            border: 1px solid var(--panel-border); border-radius: 6px; padding: 10px;
            font-family: 'Share Tech Mono', monospace; font-size: 15px; margin-bottom: 15px; outline: none;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.8);
        }
        select.target-select option { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        select.target-select option:checked { background: rgba(0, 229, 255, 0.3); color: #fff; }

        /* İstihbarat Arşivi & Mobil Kaydırılabilir Tablo */
        .table-responsive { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 6px; border: 1px solid var(--panel-border); }
        table { width: 100%; border-collapse: collapse; min-width: 800px; }
        th { background: rgba(0, 0, 0, 0.8); color: var(--text-muted); font-family: 'Share Tech Mono', monospace; padding: 15px; text-align: left; font-size: 13px; text-transform: uppercase; border-bottom: 1px solid var(--panel-border); white-space: nowrap; }
        td { padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.03); font-family: 'Share Tech Mono', monospace; font-size: 14px; background: rgba(0,0,0,0.4); transition: background 0.2s; white-space: nowrap; }
        tr:hover td { background: rgba(0, 229, 255, 0.08); }
        
        /* Metrik Kartları */
        .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .summary-card { 
            background: rgba(0,0,0,0.6); border: 1px solid var(--panel-border); 
            border-radius: 8px; padding: 20px; text-align: center; 
            box-shadow: inset 0 0 15px rgba(0,0,0,0.5);
            transition: transform 0.2s;
        }
        .summary-card:hover { transform: translateY(-5px); border-color: var(--accent-cyan); }
        .summary-card h3 { margin: 0 0 10px 0; color: var(--text-muted); font-size: 12px; font-family: 'Share Tech Mono', monospace; letter-spacing: 1px; }
        .summary-card p { margin: 0; font-size: 2.5rem; font-weight: 700; font-family: 'Rajdhani', sans-serif; text-shadow: 0 0 15px rgba(255,255,255,0.1); }
        .text-warning { color: var(--warning); text-shadow: 0 0 15px rgba(255, 183, 0, 0.3) !important; }
        .text-danger { color: var(--danger); text-shadow: 0 0 15px rgba(255, 42, 42, 0.3) !important; }
        
        .search-box { 
            width: 100%; padding: 15px; background: rgba(0,0,0,0.7); color: var(--accent-cyan); 
            border: 1px solid var(--panel-border); border-radius: 6px;
            font-family: 'Share Tech Mono', monospace; font-size: 15px;
            transition: all 0.3s; margin-bottom: 15px;
        }
        .search-box:focus { border-color: var(--accent-cyan); outline: none; box-shadow: 0 0 15px var(--accent-cyan-glow); background: #000; }
        
        /* Modern Rozetler */
        .badge { padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; }
        .bg-std { background: rgba(255,255,255,0.05); color: #aaa; border: 1px solid rgba(255,255,255,0.1); }
        .bg-ano { background: rgba(255, 183, 0, 0.1); color: var(--warning); border: 1px solid var(--warning); box-shadow: 0 0 10px rgba(255, 183, 0, 0.2); }
        .bg-alr { background: rgba(255, 42, 42, 0.1); color: var(--danger); border: 1px solid var(--danger); box-shadow: 0 0 10px var(--danger-glow); animation: pulseRed 2s infinite; }
        @keyframes pulseRed { 0% { box-shadow: 0 0 5px var(--danger-glow); } 50% { box-shadow: 0 0 15px var(--danger); } 100% { box-shadow: 0 0 5px var(--danger-glow); } }
        
        .kanit-btn { 
            color: var(--accent-cyan); text-decoration: none; font-weight: bold; 
            padding: 6px 12px; background: rgba(0, 229, 255, 0.1); border: 1px solid var(--accent-cyan); 
            border-radius: 4px; transition: all 0.2s; display: inline-block;
        }
        .kanit-btn:hover { background: var(--accent-cyan); color: #000; box-shadow: 0 0 15px var(--accent-cyan-glow); }

        /* MOBİL RESPONSIVE (Telefon ve Tablet Uyumluluğu) */
        @media (max-width: 900px) {
            .main-layout { flex-direction: column; }
            .header h2 { font-size: 1.4rem; }
            .summary-grid { grid-template-columns: 1fr; gap: 10px; }
            .summary-card p { font-size: 2rem; }
            .tabs { margin-bottom: 15px; }
            .tab-btn { padding: 10px 15px; font-size: 13px; }
            .glass-panel { padding: 15px; }
            .grid-2 { grid-template-columns: 1fr; gap: 10px; } 
        }
    </style>
</head>
<body>
    <div class="header">
        <h2><span class="live-dot"></span> OMNIVISION C2 TERMINAL</h2>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('op-tab', this)">[ OPERASYON EKRANI ]</button>
        <button class="tab-btn" onclick="switchTab('log-tab', this)">[ İSTİHBARAT ARŞİVİ ]</button>
    </div>

    <div id="op-tab" class="tab-content active">
        <div class="main-layout">
            <div class="video-column">
                <div class="video-wrapper">
                    <img id="videoStream" class="video-feed" src="/video_feed" alt="Video Sinyali Bekleniyor...">
                </div>
            </div>
            <div class="controls-column">
                <div class="glass-panel">
                    <h3>◎ RADAR KONTROLÜ</h3>
                    <button class="cmd-btn alarm" onclick="sendCommand('toggle_alarm')">🚨 ALARM (AÇ/KAPAT)</button>
                    <button class="cmd-btn" onclick="sendCommand('toggle_hud')">🖥️ HUD GİZLE/GÖSTER</button>
                    <button class="cmd-btn" onclick="sendCommand('toggle_track')">🎯 TAKİP SİSTEMİ</button>
                </div>
                
                <div class="glass-panel">
                    <h3>◉ HEDEF SEÇİMİ (ÇOKLU)</h3>
                    <select id="targetSelect" class="target-select" multiple></select>
                    <button class="cmd-btn" onclick="setTargets()">>>> HEDEFLERİ KİLİTLE <<<</button>
                </div>
                
                <div class="glass-panel">
                    <h3>🔊 SİSTEM SESİ (ANTI-SABOTAJ)</h3>
                    <div class="grid-2">
                        <button class="cmd-btn" onclick="sendCommand('vol_up')">🔊 +%10 SES</button>
                        <button class="cmd-btn" onclick="sendCommand('vol_down')">🔉 -%10 SES</button>
                    </div>
                    <button class="cmd-btn" style="border-color: #a855f7; color: #a855f7; margin-top: 12px;" onclick="sendCommand('vol_mute')">🔇 MUTE / UNMUTE</button>
                    <button class="cmd-btn override" style="margin-top: 12px;" onclick="sendCommand('vol_max')">⚠️ MAX SES (OVERRIDE)</button>
                </div>
            </div>
        </div>
    </div>

    <div id="log-tab" class="tab-content">
        <div class="summary-grid">
            <div class="summary-card">
                <h3>TOPLAM HEDEF (24H)</h3>
                <p id="sumTotal" class="text-cyan">0</p>
            </div>
            <div class="summary-card">
                <h3>ANOMALİ (24H)</h3>
                <p id="sumAnomalies" class="text-warning">0</p>
            </div>
            <div class="summary-card">
                <h3>ALARM (24H)</h3>
                <p id="sumAlarms" class="text-danger">0</p>
            </div>
        </div>
        
        <div class="glass-panel" style="margin-bottom: 20px;">
            <div style="display: flex; flex-direction: column; gap: 10px;">
                <input type="text" id="searchInput" class="search-box" style="margin: 0;" placeholder="🕵️ Sınıf veya Olay Türü Ara (Örn: PERSON veya ANOMALY)..." onkeyup="if(event.key === 'Enter') fetchLogs()">
                <div class="grid-2" style="grid-template-columns: 1fr 1fr 1fr;">
                    <button class="cmd-btn" style="margin: 0;" onclick="fetchLogs()">🔍 SORGULA</button>
                    <button class="cmd-btn" style="margin: 0; border-color: var(--success); color: var(--success);" onclick="window.location.href='/api/export_csv'">📥 EXCEL İNDİR</button>
                    <button class="cmd-btn alarm" style="margin: 0;" onclick="wipeDB()">🗑️ SİSTEMİ TEMİZLE</button>
                </div>
            </div>
        </div>

        <div class="table-responsive">
            <table id="logTable">
                <thead>
                    <tr>
                        <th>Zaman</th><th>ID</th><th>Sınıf</th><th>Tür</th><th>Süre</th><th>Güven</th><th>Koor (X,Y)</th><th>Kanıt</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        function switchTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
            if(tabId === 'log-tab') { fetchSummary(); fetchLogs(); }
        }

        async function sendCommand(action) {
            await fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: action}) });
            if (navigator.vibrate) navigator.vibrate(50);
        }

        async function setTargets() {
            const select = document.getElementById('targetSelect');
            const selectedIds = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));
            if(selectedIds.length === 0) { alert("Lütfen en az bir hedef seçin!"); return; }
            await fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'set_targets', payload: selectedIds}) });
            if (navigator.vibrate) navigator.vibrate([50, 50, 50]);
            alert("Hedefler radara iletildi.");
        }

        async function loadClasses() {
            const res = await fetch('/api/classes');
            const classes = await res.json();
            const select = document.getElementById('targetSelect');
            const sortedClasses = Object.entries(classes).sort((a, b) => a[1].localeCompare(b[1]));
            sortedClasses.forEach(([id, name]) => {
                const opt = document.createElement('option');
                opt.value = id;
                opt.innerText = `[${id.padStart(2, '0')}] ${name.toUpperCase()}`;
                select.appendChild(opt);
            });
        }

        async function fetchSummary() {
            try {
                const res = await fetch('/api/summary');
                const data = await res.json();
                document.getElementById('sumTotal').innerText = data.total;
                document.getElementById('sumAnomalies').innerText = data.anomalies;
                document.getElementById('sumAlarms').innerText = data.alarms;
            } catch (err) {}
        }

        async function fetchLogs() {
            const q = document.getElementById('searchInput').value;
            try {
                const res = await fetch(`/api/logs?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                const tbody = document.getElementById('tableBody');
                
                tbody.innerHTML = data.map(row => {
                    let badgeClass = "bg-std";
                    if(row[4] === "ANOMALY") badgeClass = "bg-ano";
                    if(row[4] === "ALARM") badgeClass = "bg-alr";
                    
                    const imgPath = row[9];
                    const imgLink = imgPath ? `<a href="/${imgPath.replace(/\\\\/g, '/')}" target="_blank" class="kanit-btn">📸 GÖR</a>` : "-";
                    
                    return `
                    <tr>
                        <td>${row[1]}</td><td>#${row[2]}</td>
                        <td style="color: var(--accent-cyan); font-weight: bold;">${row[3]}</td>
                        <td><span class="badge ${badgeClass}">${row[4]}</span></td>
                        <td>${row[5]}s</td>
                        <td>%${Math.round(row[6]*100)}</td>
                        <td>${row[7]}, ${row[8]}</td>
                        <td>${imgLink}</td>
                    </tr>
                    `;
                }).join('');
            } catch (err) {}
        }

        async function wipeDB() {
            if(confirm("Tüm istihbarat logları ve FOTOĞRAFLAR silinecek. Onaylıyor musunuz?")) {
                await fetch('/api/wipe', { method: 'DELETE' });
                fetchSummary();
                fetchLogs(); 
            }
        }

        loadClasses();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return html_content