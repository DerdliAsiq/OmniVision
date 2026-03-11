# 👁️ OMNIVISION: TACTICAL INTELLIGENCE PLATFORM (MASTER CONTEXT)

## 📌 PROJE KİMLİĞİ
* **Proje Adı:** OmniVision (Eski adıyla Aelsa-OmniVision, kurumsal ibarelerden tamamen temizlenmiş açık kaynak versiyonu).
* **Geliştirici / Mimar:** DerdliAsiq (GitHub üzerinden açık kaynak olarak yayınlanıyor).
* **Lisans:** MIT License
* **Depo:** `https://github.com/DerdliAsiq/OmniVision.git`
* **Proje Amacı:** Kritik tesislerin ve İnsansız Deniz Araçlarının (İDA) otonom gözetlenmesi için "Edge AI" prensipleriyle çalışan, donanım hızlandırmalı, düşük gecikmeli hibrit yapay zeka ve taktiksel istihbarat platformu.

---

## 💻 DONANIM VE ORTAM (HARDWARE & ENVIRONMENT)
Proje çift donanım mimarisi felsefesiyle geliştirilmektedir:

### 1. Geliştirme Ortamı (Ana Karargah)
* **İşletim Sistemi:** Garuda Linux (Arch tabanlı), Fish Shell.
* **CPU:** AMD Ryzen 5 7535HS (3.3 GHz - 4.4GHz Turbo)
* **GPU 1:** NVIDIA RTX 2050 4GB GDDR6 (CUDA - Derin öğrenme ve YOLOv8x çıkarımı için kullanılıyor)
* **GPU 2:** AMD Radeon TM Graphics 512MB
* **RAM & Depolama:** 16 GB DDR5 / 512 GB M.2 NVMe SSD
* **AI Modeli (Güncel):** `yolov8x.pt` (Extra Large - RTX 2050 üzerinde maksimum zeka için).

### 2. Hedef Ortam (Saha / İDA - İnsansız Deniz Aracı)
* **Donanım:** Raspberry Pi 5 (ARM64 / aarch64)
* **AI Modeli (Planlanan):** Pi 5'in işlem gücü kısıtlamaları nedeniyle sahaya inildiğinde model `yolov8n.pt` (Nano) veya INT8 kuantizasyonlu NCNN formatına dönüştürülerek kullanılacak.

---

## 🏗️ SİSTEM MİMARİSİ VE MODÜLLER (CORE COMPONENTS)

Sistem tamamen modüler, asenkron ve donanım darboğazlarını (bottleneck) önleyecek şekilde tasarlanmıştır.

### 1. `main.py` (Orkestratör)
Sistemin ana döngüsü. Thread'leri başlatır, FPS hesaplamasını (`time.time()`) yapar, OpenCV penceresini (`cv2.WINDOW_FULLSCREEN`) yönetir ve `config.py` üzerinden gelen klavye kısayollarını dinler.

### 2. `omni_engine.py` (Kamera Motoru)
* **Görevi:** Asenkron görüntü yakalama.
* **Detay:** Görüntü okuma işlemini kendi içinde bir Thread (iş parçacığı) olarak çalıştırır. `cv2.CAP_V4L2` (Pi 5 için) ve standart okumayı otomatik algılar. Çözünürlük 1280x720'dir. Frame dropları engellemek için `BUFFERSIZE=5` olarak ayarlanmıştır. IP kameraları (`http://ip:port/video`) destekler. Aynalama (`cv2.flip`) içerir.

### 3. `horizon_engine.py` (Dinamik Ufuk Çizgisi)
* **Görevi:** İDA'nın dalgalardaki pitch/roll hareketlerinde ufuk çizgisini bulmak.
* **Detay:** CPU tasarrufu için görüntüyü küçültür. Gaussian Blur, Canny Edge (50-150) ve HoughLinesP kullanılarak ufuk tespiti yapar. Gökyüzünü atlayarak YOLO'ya sadece deniz yüzeyini (ROI) gönderir. Dalga toleransı için 15-165 derece dışındaki çizgileri filtreler.

### 4. `omni_detector.py` (Yapay Zeka & Taktik Çizim)
* **Görevi:** YOLOv8x ile nesne tespiti ve Supervision ile hedef takibi.
* **Detay:** `horizon_engine`'den gelen Y ekseni kesimini uygular. Tespitleri `supervision` objelerine (`sv.Detections`) çevirir. `ByteTrack` ile iz sürer. `BoxAnnotator`, `LabelAnnotator` ve arkasında kuyruk bırakan `TraceAnnotator` kullanır. Kestiği Y eksenini ana ekranda doğru yere çizmek için koordinat düzeltmesi yapar. Loglama için `threats` (tehditler) listesi döndürür.

### 5. `omni_ui.py` (HUD & Telemetri)
* **Görevi:** Görüntünün sağına taktiksel bir dashboard eklemek.
* **Detay:** Numpy ile orijinal görüntüyü 320px genişletir. `psutil` kullanarak anlık CPU, RAM ve FPS değerlerini basar. Modüllerin aktif/pasif durumlarını (Tracking, LiDAR, Horizon) ve simüle edilmiş uzaklık verisini gösterir.

### 6. `omni_database.py` (Asenkron İstihbarat Loglama)
* **Görevi:** Tehditleri SQLite veritabanına kaydetmek.
* **Detay:** Veritabanı adı `tactical_vision.db`. Ana programı yavaşlatmamak için `queue.Queue()` ve `threading` kullanır. Database lock (kilitlenme) hatalarını önlemek için `PRAGMA journal_mode=WAL;` modunda çalışır. Zaman damgası, nesne ID, etiket, güven skoru ve merkez X/Y koordinatlarını kaydeder.

### 7. `tactical_web_dashboard.py` (Web Arayüzü)
* **Görevi:** FastAPI tabanlı, tarayıcı üzerinden erişilebilen modern log izleme merkezi.
* **Detay:** Uvicorn ile 8000 portunda çalışır (`http://localhost:8000`). Güven skoruna göre filtreleme, ID/Nesne arama, Dark/Light tema ve veritabanını sıfırlama (Wipe) özelliklerine sahiptir. AJAX ile sayfayı yenilemeden saniyede bir logları günceller.

### 8. `test_project.py` (Sistem Teşhisi)
* **Görevi:** Bare-metal donanım ve yazılım bütünlüğünü test etmek.
* **Detay:** 9 adımlı, decorator tabanlı bir Validation Suite. Kütüphaneleri, model dosyalarının varlığını, hata yakalama (try/except) bloklarını, threading altyapısını ve bellek sızıntılarını kontrol eder.

---

## ⚙️ YAPILANDIRMA VE KONTROLLER (HOTKEYS)
`config.py` içindeki `SystemState` sınıfına bağlı olarak, sistem çalışırken şu tuşlar aktiftir:
* `q` : Sistemi güvenli kapat.
* `d` : Sağdaki Dashboard'u aç / kapat.
* `t` : AI Nesne Takibi ve Çizimleri (Tracking) aç / kapat.
* `l` : LiDAR simülasyonunu aç / kapat.
* `p` : Performans metriklerini (CPU/RAM/FPS) aç / kapat.
* `h` : Ufuk Çizgisi tespitini ve ROI kesimini aç / kapat (İşlemci tasarruf modu).

---

## 🚀 MEVCUT DURUM VE GELECEK HEDEFLER
* **Başarılanlar:** Kurumsal ibareler temizlendi, GitHub'a pushlandı. Supervision, dinamik ufuk çizgisi ve SQLite entegrasyonu tamamen stabil. IP Kamera bağlantı altyapısı aktif. `.gitignore` yapılandırıldı (Büyük `.pt` ve `.db` dosyaları hariç tutuldu).
* **Sıradaki Adımlar / Yol Haritası:** 1. İDA üzerindeki Raspberry Pi 5 için NCNN model optimizasyonu.
    2. Supervision kütüphanesi kullanılarak denizde belirli bir bölgeye girildiğinde alarm veren "Polygon Zones" (Sanal Çit) entegrasyonu.
    3. Gerçek LiDAR veya Sonar sensör verilerinin seri port üzerinden okunup HUD üzerine entegre edilmesi.