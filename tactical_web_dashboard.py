import sqlite3
import uvicorn
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="OmniVision Modern HUD")
DB_NAME = "tactical_vision.db"

html_content = """
<!DOCTYPE html>
<html lang="tr" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OmniVision | Log Center</title>
    <style>
        :root[data-theme="dark"] {
            --bg-color: #121212; --panel-bg: #1e1e1e; --text-main: #f5f5f5;
            --border: #333; --primary: #3b82f6; --danger: #ef4444;
        }
        :root[data-theme="light"] {
            --bg-color: #f3f4f6; --panel-bg: #ffffff; --text-main: #1f2937;
            --border: #e5e7eb; --primary: #2563eb; --danger: #dc2626;
        }
        body {
            background-color: var(--bg-color); color: var(--text-main);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0; padding: 20px; transition: all 0.3s ease;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .controls { 
            background: var(--panel-bg); padding: 15px; border-radius: 8px; 
            border: 1px solid var(--border); display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap;
        }
        input, select, button {
            padding: 10px; border-radius: 6px; border: 1px solid var(--border);
            background: var(--bg-color); color: var(--text-main); font-size: 14px; outline: none;
        }
        button { cursor: pointer; font-weight: bold; border: none; transition: 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-theme { background: transparent; border: 1px solid var(--border); font-size: 18px; }
        
        table { width: 100%; border-collapse: collapse; background: var(--panel-bg); border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: rgba(59, 130, 246, 0.1); color: var(--primary); font-weight: 600; }
        .live-dot { width: 10px; height: 10px; background: #10b981; border-radius: 50%; display: inline-block; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0.4; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2><span class="live-dot"></span> OmniVision İstihbarat Merkezi</h2>
            <div>
                <button class="btn-theme" onclick="toggleTheme()" id="theme-btn">☀️</button>
                <button class="btn-danger" onclick="wipeDB()">🗑️ Veritabanını Temizle</button>
            </div>
        </div>

        <div class="controls">
            <input type="text" id="searchInput" placeholder="ID veya Nesne ara..." onkeyup="filterTable()">
            <select id="confFilter" onchange="filterTable()">
                <option value="0">Tüm Güven Skorları</option>
                <option value="50">> %50 Güven</option>
                <option value="80">> %80 Güven</option>
            </select>
        </div>

        <table id="logTable">
            <thead>
                <tr>
                    <th>Zaman</th>
                    <th>ID</th>
                    <th>Nesne (Label)</th>
                    <th>Güven Skoru</th>
                    <th>Koordinat (X, Y)</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>

    <script>
        let allData = [];

        function toggleTheme() {
            const html = document.documentElement;
            const btn = document.getElementById('theme-btn');
            if(html.getAttribute('data-theme') === 'dark') {
                html.setAttribute('data-theme', 'light');
                btn.innerText = '🌙';
            } else {
                html.setAttribute('data-theme', 'dark');
                btn.innerText = '☀️';
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                allData = await res.json();
                filterTable(); 
            } catch (err) { console.error("Veri çekilemedi", err); }
        }

        function filterTable() {
            const searchText = document.getElementById('searchInput').value.toLowerCase();
            const minConf = parseInt(document.getElementById('confFilter').value);
            
            const tbody = document.getElementById('tableBody');
            let newHTML = '';

            allData.forEach(row => {
                const confPercent = Math.round(row[4] * 100);
                const searchMatch = row[2].toString().includes(searchText) || row[3].toLowerCase().includes(searchText);
                const confMatch = confPercent >= minConf;

                if(searchMatch && confMatch) {
                    newHTML += `<tr>
                        <td>${row[1]}</td>
                        <td><strong>#${row[2]}</strong></td>
                        <td style="text-transform: capitalize;">${row[3]}</td>
                        <td>%${confPercent}</td>
                        <td>${row[5]}, ${row[6]}</td>
                    </tr>`;
                }
            });
            tbody.innerHTML = newHTML;
        }

        async function wipeDB() {
            if(confirm("Tüm loglar kalıcı olarak silinecektir. Emin misiniz?")) {
                await fetch('/api/wipe', { method: 'DELETE' });
                fetchLogs(); 
            }
        }

        setInterval(fetchLogs, 1000);
        window.onload = fetchLogs;
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return html_content

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

if __name__ == "__main__":
    print("[+] Modern OmniVision Web Sunucusu Başlatılıyor...")
    uvicorn.run(app, host="0.0.0.0", port=8000)