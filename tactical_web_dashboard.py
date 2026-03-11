import sqlite3
import cv2
import threading
import os
import asyncio
import subprocess
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from config import SystemState

app = FastAPI(title="OmniVision C2 Merkezi")
DB_NAME = "tactical_vision.db"

# --- CANLI YAYIN (MJPEG STREAMING) TAMPONU ---
latest_frame = None
frame_lock = threading.Lock()

def update_video_frame(frame):
    """main.py'den gelen son görüntüyü web sunucusunun tamponuna yazar."""
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()

async def video_generator():
    """Web tarayıcısına ASENKRON (Low-Latency) video akışı sağlar."""
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
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        await asyncio.sleep(0.03)

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


# --- API UZAKTAN KUMANDA VE OS SES KONTROLÜ ---
class CommandData(BaseModel):
    action: str
    payload: list = None

@app.post("/api/command")
async def execute_command(cmd: CommandData):
    action = cmd.action
    
    # 1. Radar Kontrolleri
    if action == "toggle_alarm":
        SystemState.ALARM_MODE = not SystemState.ALARM_MODE
    elif action == "toggle_hud":
        SystemState.SHOW_DASHBOARD = not SystemState.SHOW_DASHBOARD
    elif action == "toggle_track":
        SystemState.TRACKING_ACTIVE = not SystemState.TRACKING_ACTIVE
    elif action == "toggle_horizon":
        SystemState.HORIZON_SCAN_ACTIVE = not SystemState.HORIZON_SCAN_ACTIVE
    elif action == "set_targets" and cmd.payload is not None:
        SystemState.ACTIVE_TARGET_IDS = cmd.payload
        SystemState.ACTIVE_TARGET_NAMES = [SystemState.MODEL_CLASSES[i].upper() for i in cmd.payload]
        
    # 2. İşletim Sistemi Ses (Anti-Sabotaj) Kontrolleri - GARUDA LINUX UYUMLU (Saf Shell Modu)
    elif action == "vol_up":
        subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ +10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_down":
        subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ -10%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_mute":
        subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ toggle", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "vol_max":
        # Önce sessizi kaldır (unmute), sonra %100'e daya
        subprocess.Popen("pactl set-sink-mute @DEFAULT_SINK@ 0", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen("pactl set-sink-volume @DEFAULT_SINK@ 100%", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    return {"status": "success", "action": action}

@app.get("/api/classes")
async def get_model_classes():
    return SystemState.MODEL_CLASSES

@app.get("/api/logs")
async def get_logs():
    if not os.path.exists(DB_NAME): return []
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("SELECT * FROM threat_logs ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e: return []

@app.delete("/api/wipe")
async def wipe_database():
    if os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM threat_logs")
        conn.commit()
        conn.close()
    return {"status": "cleared"}


# --- SİBERPUNK WEB ARAYÜZÜ (HTML/JS) ---
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
        }
        body {
            background-color: var(--bg-color); color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0; padding: 15px;
        }
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

        table { width: 100%; border-collapse: collapse; background: var(--panel-bg); }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--accent); }
        
        @media (max-width: 800px) { .grid-container { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h2><span class="live-dot"></span> OMNIVISION C2 TERMINAL</h2>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('op-tab', this)">[ OPERASYON EKRANI ]</button>
        <button class="tab-btn" onclick="switchTab('log-tab', this)">[ İSTİHBARAT LOGLARI ]</button>
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
                <button class="cmd-btn" onclick="sendCommand('toggle_horizon')">🌊 UFUK ÇİZGİSİ</button>
                
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
        <button onclick="wipeDB()" style="padding:10px; background:var(--danger); color:white; border:none; cursor:pointer; margin-bottom:15px;">🗑️ VERİTABANINI TEMİZLE</button>
        <table id="logTable">
            <thead>
                <tr>
                    <th>Zaman</th><th>ID</th><th>Sınıf</th><th>Güven</th><th>Koor (X,Y)</th>
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
        }

        async function sendCommand(action) {
            await fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: action})
            });
        }

        async function setTargets() {
            const select = document.getElementById('targetSelect');
            const selectedIds = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));
            if(selectedIds.length === 0) { alert("Lütfen en az bir hedef seçin!"); return; }
            
            await fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'set_targets', payload: selectedIds})
            });
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

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                const data = await res.json();
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = data.map(row => `
                    <tr>
                        <td>${row[1]}</td><td>#${row[2]}</td>
                        <td>${row[3].toUpperCase()}</td><td>%${Math.round(row[4]*100)}</td>
                        <td>${row[5]}, ${row[6]}</td>
                    </tr>
                `).join('');
            } catch (err) {}
        }

        async function wipeDB() {
            if(confirm("Tüm istihbarat logları silinecek. Onaylıyor musunuz?")) {
                await fetch('/api/wipe', { method: 'DELETE' });
                fetchLogs(); 
            }
        }

        loadClasses();
        setInterval(fetchLogs, 1500); 
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return html_content