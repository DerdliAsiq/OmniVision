import sqlite3
import threading
import queue
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

class OmniDatabase:
    def __init__(self, db_name="tactical_vision.db"):
        self.db_name = db_name
        self.log_queue = queue.Queue()
        self.is_running = True
        
        self._create_tables()
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("[+] SQL Veritabanı Motoru Başlatıldı: Asenkron Kayıt Aktif.")

    def _create_tables(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;") 
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS threat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    object_id INTEGER,
                    label TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    x_center INTEGER,
                    y_center INTEGER
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[X] Veritabanı oluşturma hatası: {e}")

    def log_threat(self, object_id, label, confidence, bbox):
        x_center = int((bbox[0] + bbox[2]) / 2)
        y_center = int((bbox[1] + bbox[3]) / 2)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        payload = (timestamp, object_id, label, float(confidence), x_center, y_center)
        self.log_queue.put(payload)

    def _process_queue(self):
        conn = sqlite3.connect(self.db_name, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        while self.is_running:
            try:
                data = self.log_queue.get(timeout=1)
                cursor.execute('''
                    INSERT INTO threat_logs (timestamp, object_id, label, confidence, x_center, y_center)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', data)
                conn.commit()
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[X] SQL Yazma Hatası: {e}")
                
        conn.close()

    def stop(self):
        self.is_running = False
        self.worker_thread.join(timeout=3)
        logger.info("[+] Veritabanı Bağlantısı Güvenli Şekilde Kapatıldı.")