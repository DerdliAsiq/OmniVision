# Aelsa-OmniVision | Proje Teknik Dokümantasyonu ve Sistem Hafızası

**Geliştirici:** Berzamin Cyber (Persona: Vigilante)  
**Sistem:** AELSA Defence / AELSA TECNOLOGIES
**Versiyon:** 1.3.0-ProductionReady  
**Donanım Altyapısı:** AMD Ryzen 5 7535HS, RTX 2050 4GB GPU, 16 GB DDR5 RAM (Geliştirme Ortamı: Ubuntu Sanal Makine)

---

## 1. Sistemin Mevcut Durumu ve Özeti
Aelsa-OmniVision, sıfırdan inşa edilmiş, asenkron multi-threading kamera okuma altyapısına sahip, yapay zeka (YOLOv8) destekli ve askeri standartlarda (Mil-Spec) tasarlanmış bir "Taktiksel Gözetim ve Tehdit Algılama" sistemidir. Proje, tek bir Python dosyasından çıkarılarak tamamen modüler, hata toleranslı (try-except korumalı) ve üretime hazır (Production-Ready) bir mimariye geçirilmiştir.

## 2. Modüler Dosya Mimarisi (V1.3)
Sistem "Modüler Savunma" prensibiyle aşağıdaki dosyalara bölünmüştür:

* **`config.py`**: Sistem durum yönetimi. Klavye kısayol bayrakları (D: Dashboard, T: Tracking, vb.), donanım çözünürlük ayarları (`SCREEN_WIDTH`, `SCREEN_HEIGHT`) ve LiDAR simülasyon parametreleri burada tutulur.
* **`omni_engine.py`**: Görüntü yakalama motoru. `BUFFERSIZE=5` optimizasyonu, thread zaman aşımı koruması (timeout=5) ve kameradan gelen görüntüyü gerçek dünya ile eşleyen yatay aynalama (`cv2.flip`) işlemleri burada yapılır.
* **`omni_detector.py`**: Yapay Zeka çekirdeği. `yolov8n.pt` (Nano) modeli kullanılarak CPU/VM darboğazı engellenmiştir. `ByteTrack` algoritması (`persist=True`) ile titreşimsiz ve ID atamalı hedef takibi yapılır. Çözünürlük optimizasyonu için `imgsz=320` kullanılır.
* **`omni_ui.py`**: Taktiksel Bölünmüş Ekran (Split-Screen) Arayüzü. `WINDOW_FREERATIO` kullanılarak Ubuntu/Linux sistemlerindeki beyaz kenar boşlukları (letterboxing) yok edilmiştir. Canlı donanım metrikleri (CPU, RAM, FPS) grafiksel barlarla ve siber-taktiksel bir renk paletiyle (Antrasit, Siber Mavi, Hacker Yeşili) ekrana yansıtılır.
* **`main.py`**: Orkestratör. Kamera ısınma protokolünü (warm-up), global hata yakalama bloklarını ve klavye girdilerini yönetir.
* **`test_project.py`**: Vigilante V3.0 Derin Teşhis Motoru. Tkinter tabanlı GUI ile sistemin bağımlılıklarını, donanımlarını (Kamera, RAM, GPU), ağ bağlantılarını ve dosya izinlerini 100 farklı noktadan asenkron olarak tarar. Hata durumunda "Otonom Çözüm Önerileri" sunar.

## 3. Uygulanan Kritik Güvenlik ve Performans Yamaları
1.  **Thread Güvenliği:** Kapanışlarda askıda kalan (zombie) thread'leri engellemek için `join()` komutlarına zaman aşımı eklendi.
2.  **Kapsamlı Tehdit Algılama:** AI döngüsündeki erken `return` hatası düzeltilerek ekrandaki tüm nesnelerin (çoklu hedef) aynı anda işlenmesi sağlandı.
3.  **Fikri Mülkiyet:** AELSA Technologies standartlarında kurumsal `LICENSE` dosyası ve `__init__.py` paket yapısı oluşturuldu. Sürüm bağımlılıkları `requirements.txt` içine sabitlendi.
4.  **UI/UX Mükemmelliği:** Yazı tiplerine Anti-Aliasing (`cv2.LINE_AA`) uygulandı ve UI tamamen dinamik/bölünmüş ekran tuvaline (`numpy.zeros`) taşındı.

## 4. Yol Haritası (Roadmap) - Sıradaki Adım
Sistem donanımsal ve yazılımsal olarak 100 testten başarıyla geçmiş ve tamamen stabil hale gelmiştir. 

**Bir Sonraki Operasyon (Sıradaki Hedef): Veritabanı Loglama (SQL Threat Logging)**
* Ekranda tespit edilen her bir hedefin (Person, vb.) ID'si.
* Tespit edilme zamanı (Timestamp).
* Görseldeki koordinatları ve güven skoru (Confidence).
* Bu verilerin yerel bir `SQLite3` (veya hedeflenen başka bir SQL) veritabanına, sistem performansını (FPS) düşürmeden asenkron olarak kaydedilmesi planlanmaktadır.