Gemini şunu dedi:
Aelsa-OmniVision | Proje Teknik Dokümantasyonu (proje.md)

Berzamin Cyber, operasyonun bu aşamasında projenin tüm teknik detaylarını, mimari felsefesini ve gelecek vizyonunu içeren kapsamlı bir dökümantasyon hazırladım. Bu dosya, AELSA Defence bünyesindeki geliştirme süreçlerini standartlaştırmak ve projenin profesyonel bir temele oturmasını sağlamak içindir.
👁️ Aelsa-OmniVision Teknik Raporu

Geliştirici: Berzamin Cyber

Sistem: AELSA Defence / Kiber Guard Akademiyası

Versiyon: 1.0.0-Alpha

Tarih: 28 Şubat 2026
1. Şimdiye Kadar Yapılanlar

Projenin temel yapı taşları sıfırdan inşa edilmiş ve operasyonel hale getirilmiştir:

    Mimari Tasarım: Proje ismi Aelsa-OmniVision olarak belirlenmiş ve mülkiyet hakları AELSA Technologies altında koruma altına alınmıştır.

    Donanım Farkındalığı: AMD Ryzen 5 7535HS ve RTX 2050 donanım mimarisini tanıyan, aynı zamanda Raspberry Pi 5 (ARM64) ile tam uyumlu çalışan bir çekirdek geliştirilmiştir.

    Omni-Engine: Görüntü yakalama işlemini ana iş parçacığından ayıran Multi-threading yapısı kurulmuştur. Bu sayede sıfır gecikmeli (Zero-lag) görüntü akışı sağlanmıştır.

    Neural-Shield Entegrasyonu: YOLOv8-Nano modeli sisteme entegre edilerek gerçek zamanlı nesne tanıma kabiliyeti kazandırılmıştır.

    Geliştirme Ortamı: Kali Linux üzerinde izole bir sanal ortam (venv) oluşturulmuş ve bağımlılıklar (OpenCV, Ultralytics, Supervision) optimize edilmiştir.

2. Kodun Yazım Mimarisi

Kod, "Modüler Savunma" prensibiyle iki ana katman üzerine inşa edilmiştir:
A. Veri Toplama Katmanı (OmniEngine)

    Asenkron Yapı: Kamera okuma hızı, işlemci analiz hızından bağımsızdır. _update metodu arka planda sürekli en taze kareyi tamponda tutar.

    Dinamik Sürücü Seçimi: Sistem Pi 5 algıladığında V4L2 sürücüsünü, PC algıladığında MSMF/DirectShow sürücüsünü otomatik seçer.

B. Analiz Katmanı (OmniDetector)

    Inference Pipeline: Görüntü pikselleri sinirsel ağdan (YOLO) geçerken stream=True parametresiyle bellek tüketimi minimize edilir.

    Görselleştirme: Tanınan nesneler (İnsan, araç vb.) profesyonel taktiksel çerçevelerle işaretlenir.

3. Güvenlik Odaklı Kod Yazım Protokolü

Sistem bir "Red Team" perspektifiyle geliştirilmelidir. Kod güvenliği için şu standartlar uygulanmıştır/uygulanacaktır:

    Zero-Trust Input: Kamera kaynağından gelen her kare, bellekte taşmaya (Buffer Overflow) neden olmayacak şekilde sınırlandırılmış tamponlarda işlenir.

    Proprietary Protection: Her dosya başında mülkiyet header'ı bulunur. İlerleyen aşamalarda kodun tersine mühendisliğe karşı korunması için Obfuscation (kod karartma) uygulanacaktır.

    Sanal Ortam İzolasyonu: Bağımlılıkların sistem genelini etkilememesi ve dış kütüphane açıklarından korunmak için her zaman güncel venv kullanılmalıdır.

    Gelecek Hedefi (Secure Stream): Görüntü verisi ağ üzerinden aktarılacaksa mutlaka AES-256 şifreleme katmanından geçmelidir.

4. Geliştirme ve Gelecek Planları (Roadmap)
Kısa Vadeli (Hemen Yapılacaklar)

    Supervision Entegrasyonu: Nesnelerin sadece kutu içine alınması değil, hareket yörüngelerinin (Tracking Trace) çizilmesi.

    Zone Counting: Belirlenen kritik bölgelere giriş yapıldığında görsel alarm tetiklenmesi.

Orta Vadeli (Genişleme)

    Web Dashboard: FastAPI kullanılarak görüntü akışının şifreli bir web arayüzünden izlenmesi.

    Veritabanı Loglama: Algılanan tehditlerin (zaman, konum, nesne türü) bir SQL veritabanına kaydedilmesi.

Uzun Vadeli (Vigilante Vizyonu)

    Face-ID Entegrasyonu: Berzamin Cyber'ı "Yetkili Kullanıcı" olarak tanıyan, yabancıları "Tehdit" olarak etiketleyen biyometrik katman.

    Edge-Swarm: Birden fazla Pi 5 ünitesinin merkezi bir Aelsa-OmniVision sunucusuna veri aktardığı ağ mimarisi.

5. Daha Fazla Geliştirme İçin Tavsiyeler

    Performans: RTX 2050'nin CUDA çekirdeklerini tam kapasite kullanmak için onnxruntime-gpu kütüphanesine geçiş yapılmalıdır.

    Hata Ayıklama: Sistem logları için standart print yerine Python logging modülü kullanılmalı, loglar şifreli dosyalarda tutulmalıdır.

    Donanım: Pi 5 tarafında ısınmayı önlemek için aktif soğutma kontrolü kod içerisine (GPIO üzerinden) dahil edilmelidir.

Chief Developer: Berzamin Cyber

Advisory: Vigilante AI (Co-Founder)