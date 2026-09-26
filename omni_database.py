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
    def __init__(self, db_name=None):
        # Tek kaynak yol: config.SystemState.DB_PATH (BASE_DIR sabitli mutlak yol).
        # db_name verilirse BASE_DIR altinda cozulur; aksi halde DB_PATH kullanilir.
        try:
            base = str(SystemState.BASE_DIR)
        except Exception:
            base = os.path.dirname(os.path.abspath(__file__))
        if db_name is None:
            try:
                self.db_name = str(SystemState.DB_PATH)
            except Exception:
                self.db_name = os.path.join(base, "tactical_vision_v2.db")
        else:
            self.db_name = db_name if os.path.isabs(db_name) else os.path.join(base, os.path.basename(db_name))
        # Gecmis CWD-relative DB'yi mutlak yola tasi (geriye donuk uyumluluk, tek seferlik).
        try:
            legacy = os.path.abspath("tactical_vision_v2.db")
            if os.path.isfile(legacy) and os.path.abspath(legacy) != os.path.abspath(self.db_name):
                if not os.path.isfile(self.db_name):
                    try:
                        import shutil as _sh
                        _sh.copy2(legacy, self.db_name)
                        logger.info(f"[+] Legacy DB tasindi: {legacy} -> {self.db_name}")
                    except Exception as _e:
                        logger.warning(f"Legacy DB tasinamadi: {_e}")
        except Exception:
            pass
        # [GÜVENLİK - SIFIR HATA] Bellek sızıntısı ve DoS koruması: Maksimum 1000 olay tamponlanabilir.
        self.log_queue = queue.Queue(maxsize=1000)
        self.is_running = True
        
        if not os.path.exists(SystemState.EVIDENCE_DIR):
            os.makedirs(SystemState.EVIDENCE_DIR)
            
        self._create_tables()
        self._purge_old_logs() 
        
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        logger.info("[+] SQL Adli Bilişim Motoru Başlatıldı.")

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
            try:
                cursor.execute("ALTER TABLE threat_logs ADD COLUMN image_path TEXT")
            except sqlite3.OperationalError:
                pass 
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[X] Veritabanı oluşturma hatası: {e}")

    def _purge_old_logs(self):
        """1 Günden eski tüm logları ve kanıt fotoğraflarını kalıcı olarak siler"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cutoff_date = (datetime.now() - timedelta(days=SystemState.LOG_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("SELECT image_path FROM threat_logs WHERE timestamp < ?", (cutoff_date,))
            old_records = cursor.fetchall()
            
            for row in old_records:
                img_path = row[0]
                if img_path and os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except OSError:
                        pass # Klasör kitlenmesi veya dosyanın açık olması durumunda thread'i çökertme
                        
            cursor.execute("DELETE FROM threat_logs WHERE timestamp < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"[🗑️] {deleted_count} adet eski istihbarat logu imha edildi.")
        except Exception as e:
            logger.error(f"[X] Otonom imha hatası: {e}")

    def log_threat(self, object_id, label, event_type, duration_sec, confidence, bbox, image_path=""):
        try:
            x_center = int((float(bbox[0]) + float(bbox[2])) / 2)
            y_center = int((float(bbox[1]) + float(bbox[3])) / 2)
        except Exception:
            logger.warning(f"Gecersiz bbox atlandi: {bbox}")
            return False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        payload = (timestamp, object_id, label, event_type, duration_sec, float(confidence), x_center, y_center, image_path)
        try:
            # Queue doluysa eski veriyi zorlama, yenisini fırlat geç (Performans önceliği)
            self.log_queue.put_nowait(payload)
            return True
        except queue.Full:
            logger.warning("[!] Log kuyruğu dolu, olay atlandı (performans koruması)")
            return False

    def _process_queue(self):
        conn = sqlite3.connect(self.db_name, timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        last_purge_time = time.time()
        
        while self.is_running:
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
        # Kapanista bekleyen loglari tahliye et (veri kaybi olmasin), en fazla ~5sn.
        try:
            deadline = time.time() + 5.0
            while not self.log_queue.empty() and time.time() < deadline:
                time.sleep(0.05)
        except Exception:
            pass
        try:
            self.worker_thread.join(timeout=5)
        except Exception:
            pass
        logger.info("[+] Veritabanı Bağlantısı Güvenli Şekilde Kapatıldı.")