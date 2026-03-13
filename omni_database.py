import sqlite3
import threading
import queue
import os
import time
from datetime import datetime, timedelta
import logging
from config import SystemState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OmniVision")

class OmniDatabase:
    def __init__(self, db_name="tactical_vision_v2.db"):
        self.db_name = db_name
        self.log_queue = queue.Queue()
        self.is_running = True
        
        # Kanıt klasörünü oluştur
        if not os.path.exists(SystemState.EVIDENCE_DIR):
            os.makedirs(SystemState.EVIDENCE_DIR)
            
        self._create_tables()
        self._purge_old_logs() # Sistem başlarken 1 günlük çöpleri temizle
        
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("[+] SQL Adli Bilişim Motoru (V2) Başlatıldı.")

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
                    event_type TEXT NOT NULL,
                    duration_sec INTEGER,
                    confidence REAL NOT NULL,
                    x_center INTEGER,
                    y_center INTEGER,
                    image_path TEXT
                )
            ''')
            
            # Eğer eski veritabanında image_path sütunu yoksa, sistemi çökertmeden sütunu ekle
            try:
                cursor.execute("ALTER TABLE threat_logs ADD COLUMN image_path TEXT")
            except sqlite3.OperationalError:
                pass # Sütun zaten var
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[X] Veritabanı oluşturma hatası: {e}")

    def _purge_old_logs(self):
        """1 Günden eski tüm logları ve kanıt fotoğraflarını kalıcı olarak siler"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Zaman sınırını hesapla (Örn: Şu an - 1 Gün)
            cutoff_date = (datetime.now() - timedelta(days=SystemState.LOG_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Önce silinecek fotoğrafların yollarını al ve diskten sil
            cursor.execute("SELECT image_path FROM threat_logs WHERE timestamp < ?", (cutoff_date,))
            old_records = cursor.fetchall()
            
            for row in old_records:
                img_path = row[0]
                if img_path and os.path.exists(img_path):
                    os.remove(img_path)
                    logger.info(f"[🗑️] Eski kanıt imha edildi: {img_path}")
                    
            # Sonra veritabanındaki log satırlarını sil
            cursor.execute("DELETE FROM threat_logs WHERE timestamp < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"[🗑️] {deleted_count} adet eski istihbarat logu imha edildi (Politika: {SystemState.LOG_RETENTION_DAYS} Gün).")
        except Exception as e:
            logger.error(f"[X] Otonom imha hatası: {e}")

    def log_threat(self, object_id, label, event_type, duration_sec, confidence, bbox, image_path=""):
        x_center = int((bbox[0] + bbox[2]) / 2)
        y_center = int((bbox[1] + bbox[3]) / 2)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        payload = (timestamp, object_id, label, event_type, duration_sec, float(confidence), x_center, y_center, image_path)
        self.log_queue.put(payload)

    def _process_queue(self):
        conn = sqlite3.connect(self.db_name, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        last_purge_time = time.time()
        
        while self.is_running:
            # Arka planda her saat başı temizlik kontrolü yap
            if time.time() - last_purge_time > 3600:
                self._purge_old_logs()
                last_purge_time = time.time()
                
            try:
                data = self.log_queue.get(timeout=1)
                cursor.execute('''
                    INSERT INTO threat_logs (timestamp, object_id, label, event_type, duration_sec, confidence, x_center, y_center, image_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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