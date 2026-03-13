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

# Kanıt klasörünü Web Sunucusuna tanıtıyoruz ki resimler internette görünebilsin
if not os.path.exists(SystemState.EVIDENCE_DIR):
    os.makedirs(SystemState.EVIDENCE_DIR)
app.mount(f"/{SystemState.EVIDENCE_DIR}", StaticFiles(directory=SystemState.EVIDENCE_DIR), name="evidence")

latest_frame = None
frame_lock = threading.Lock()

def update_video_frame(frame):
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()

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
        # image_path (sütun 9) artık çekiliyor
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
        
        # Silerken fotoğrafları da diskten tamamen temizle
        if os.path.exists(SystemState.EVIDENCE_DIR):
            for f in os.listdir(SystemState.EVIDENCE_DIR):
                os.remove(os.path.join(SystemState.EVIDENCE_DIR, f))
    return {"status": "cleared"}

html_content = """
<!DOCTYPE html>
<html lang="tr" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OmniVision | C2 Command</title>
    <style>
        :root[data-theme="dark"] {
            --bg-color: #0a0a0a; --panel-bg: #141414; --text-main: #00ff00;
            --border: #333; --primary: #8b0000; --danger: #ef4444; --accent: #00ffff;
            --warning: #f59e0b;
        }
        body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Courier New', Courier, monospace; margin: 0; padding: 15px; }
        .header { display: flex; justify-content: space-between; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-bottom: 15px; }
        .live-dot { width: 12px; height: 12px; background: #ef4444; border-radius: 50%; display: inline-block; animation: blink 1s infinite; margin-right: 10px; }
        @keyframes blink { 50% { opacity: 0.3; } }
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; }
        .tab-btn { background: var(--panel-bg); color: var(--text-main); border: 1px solid var(--border); padding: 10px 20px; cursor: pointer; font-weight: bold; }
        .tab-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .grid-container { display: grid; grid-template-columns: 3fr 1fr; gap: 15px; }
        .video-feed { width: 100%; border: 2px solid var(--border); border-radius: 4px; background: #000; }
        .control-panel { background: var(--panel-bg); border: 1px solid var(--border); padding: 15px; }
        button.cmd-btn { width: 100%; padding: 12px; margin-bottom: 10px; background: #222; color: #fff; border: 1px solid var(--accent); cursor: pointer; font-family: inherit; font-weight: bold; transition: 0.2s; }
        button.cmd-btn:hover { background: var(--accent); color: #000; }
        button.cmd-btn.alarm { border-color: var(--danger); }
        button.cmd-btn.alarm:hover { background: var(--danger); color: #fff; }
        button.cmd-btn.override { background: #450a0a; border-color: var(--danger); }
        button.cmd-btn.override:hover { background: var(--danger); }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        select.target-select { width: 100%; height: 120px; background: #000; color: #00ff00; border: 1px solid var(--border); font-family: inherit; margin-bottom: 10px; }
        
        table { width: 100%; border-collapse: collapse; background: var(--panel-bg); margin-top: 15px;}
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--accent); }
        
        .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
        .summary-card { background: #111; border: 1px solid var(--border); padding: 15px; text-align: center; }
        .summary-card h3 { margin: 0 0 10px 0; color: #aaa; font-size: 14px; }
        .summary-card p { margin: 0; font-size: 24px; font-weight: bold; }
        .text-warning { color: var(--warning); }
        .text-danger { color: var(--danger); }
        
        .search-box { width: 100%; padding: 12px; background: #000; color: #0f0; border: 1px solid var(--border); font-family: inherit; box-sizing: border-box; }
        
        .badge { padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;}
        .bg-std { background: #333; color: white; }
        .bg-ano { background: var(--warning); color: black; }
        .bg-alr { background: var(--danger); color: white; }
        .kanit-btn { color: #00ffff; text-decoration: none; font-weight: bold; }
        .kanit-btn:hover { color: #fff; }
        
        @media (max-width: 800px) { .grid-container, .summary-grid { grid-template-columns: 1fr; } }
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
        <div class="grid-container">
            <div>
                <img id="videoStream" class="video-feed" src="/video_feed" alt="Video Sinyali Bekleniyor...">
            </div>
            <div class="control-panel">
                <h3 style="margin-top:0; color:var(--accent);">RADAR KONTROLÜ</h3>
                <button class="cmd-btn alarm" onclick="sendCommand('toggle_alarm')">🚨 ALARM (AÇ/KAPAT)</button>
                <button class="cmd-btn" onclick="sendCommand('toggle_hud')">🖥️ HUD GİZLE/GÖSTER</button>
                <button class="cmd-btn" onclick="sendCommand('toggle_track')">🎯 TAKİP SİSTEMİ</button>
                
                <hr style="border-color: var(--border); margin: 15px 0;">
                
                <h3 style="margin-top:0; color:var(--accent);">HEDEF SEÇİMİ (ÇOKLU)</h3>
                <select id="targetSelect" class="target-select" multiple></select>
                <button class="cmd-btn" onclick="setTargets()">>>> HEDEFLERİ KİLİTLE <<<</button>
                
                <hr style="border-color: var(--border); margin: 15px 0;">
                
                <h3 style="margin-top:0; color:var(--accent);">SİSTEM SESİ (ANTI-SABOTAJ)</h3>
                <div class="grid-2">
                    <button class="cmd-btn" onclick="sendCommand('vol_up')">🔊 +%10 SES</button>
                    <button class="cmd-btn" onclick="sendCommand('vol_down')">🔉 -%10 SES</button>
                </div>
                <button class="cmd-btn" style="border-color: #a855f7;" onclick="sendCommand('vol_mute')">🔇 MUTE / UNMUTE</button>
                <button class="cmd-btn override" onclick="sendCommand('vol_max')">⚠️ MAX SES (OVERRIDE)</button>
            </div>
        </div>
    </div>

    <div id="log-tab" class="tab-content">
        <div class="summary-grid">
            <div class="summary-card">
                <h3>GÖRÜLEN TOPLAM HEDEF (24H)</h3>
                <p id="sumTotal" class="text-main">0</p>
            </div>
            <div class="summary-card">
                <h3>OYALANMA / ANOMALİ (24H)</h3>
                <p id="sumAnomalies" class="text-warning">0</p>
            </div>
            <div class="summary-card">
                <h3>KİLİTLENEN ALARMLAR (24H)</h3>
                <p id="sumAlarms" class="text-danger">0</p>
            </div>
        </div>
        
        <div class="grid-2" style="margin-bottom: 15px;">
            <input type="text" id="searchInput" class="search-box" placeholder="🕵️ Sınıf veya Olay Türü Ara (Örn: PERSON veya ANOMALY)..." onkeyup="if(event.key === 'Enter') fetchLogs()">
            <div style="display:flex; gap:10px;">
                <button onclick="fetchLogs()" style="flex:1; padding:12px; background:#222; color:#0f0; border:1px solid #0f0; cursor:pointer; font-weight:bold;">🔍 SORGULA</button>
                <button onclick="window.location.href='/api/export_csv'" style="flex:1; padding:12px; background:#0f4d0f; color:white; border:1px solid #0f0; cursor:pointer; font-weight:bold;">📥 EXCEL/CSV İNDİR</button>
                <button onclick="wipeDB()" style="padding:12px; background:var(--danger); color:white; border:none; cursor:pointer;">🗑️ SİL</button>
            </div>
        </div>

        <table id="logTable">
            <thead>
                <tr>
                    <th>Zaman</th><th>ID</th><th>Sınıf</th><th>Tür</th><th>Süre</th><th>Güven</th><th>Koor (X,Y)</th><th>Kanıt</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
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
        }

        async function setTargets() {
            const select = document.getElementById('targetSelect');
            const selectedIds = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));
            if(selectedIds.length === 0) { alert("Lütfen en az bir hedef seçin!"); return; }
            await fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'set_targets', payload: selectedIds}) });
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
                    
                    // Resim yolu varsa "GÖR" butonu ekle
                    const imgPath = row[9];
                    const imgLink = imgPath ? `<a href="/${imgPath.replace(/\\\\/g, '/')}" target="_blank" class="kanit-btn">📸 GÖR</a>` : "-";
                    
                    return `
                    <tr>
                        <td>${row[1]}</td><td>#${row[2]}</td>
                        <td><b>${row[3]}</b></td>
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