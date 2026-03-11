# 👁️ OmniVision: Tactical C2 Edition

**State-of-the-Art Neural Surveillance & Command Control Platform**

OmniVision, kritik tesislerin ve operasyonel sahaların otonom gözetlenmesi için geliştirilmiş hibrit bir yapay zeka platformudur. DerdliAsiq tarafından açık kaynak dünyasına kazandırılan bu sistem; düşük gecikmeli nesne takibi, dinamik çevre güvenliği ve donanım hızlandırmalı analiz katmanlarını bir arada sunar. 

V1.2 güncellemeleriyle birlikte sistem, yerel bir tespit yazılımı olmaktan çıkmış; tam asenkron çalışan **C2 (Command & Control) Web Terminali** ile donatılmış gerçek bir uzaktan komuta merkezine dönüşmüştür.

---

## 🚨 Yeni Nesil Taktiksel Özellikler

* **C2 Web Dashboard (Uzaktan Komuta):** FastAPI tabanlı, asenkron `asyncio` motoru ile çalışan modern kontrol paneli. Ana yapay zeka döngüsünü (OpenCV) yormadan, sıfır gecikmeli (low-latency) MJPEG canlı video akışı sağlar.
* **Anti-Sabotaj Ses Protokolü (OS Override):** Garuda Linux (PipeWire/PulseAudio) çekirdeğine doğrudan hükmeden `pactl` entegrasyonu. Ana makine fiziki olarak sessize alınsa bile, uzaktan **MAX SES (OVERRIDE)** komutu ile sistemi %100 güçte tetikleme yeteneği.
* **Kinetik Flaşör (Target Lock-on):** Radara giren tehditleri izlerken "tünel vizyonunu" önleyen çoklu tarama mimarisi. Seçili hedeflerin üzerine saniyede 6 kez Kırmızı/Siyah çakar (strobe) efekti ve taktiksel nişangah atarak operatörün dikkatini doğrudan merkeze çeker.
* **Dinamik Hedef Seçim Radarı (Tkinter):** 80 farklı COCO sınıfı arasında anlık filtreleme yapabilen, A-Z alfabetik sıralı ve "Demir Hafızalı" (önceki seçimleri unutmayan) taktiksel hedef arayüzü.
* **Akıllı Ses Kilidi (Smart Audio Lock):** Subprocess tabanlı akıllı alarm motoru. CPU'yu boğan kör döngüler yerine, seslerin üst üste binmesini (%0 overlap) fiziksel olarak engelleyen I/O optimizasyonu.
* **Horizon Scanner (Ufuk Çizgisi Motoru):** İnsansız Deniz Araçları (İDA) ve stabil olmayan kameralar için dinamik ufuk çizgisi tespiti yapar. Gökyüzünü ROI (Region of Interest) alanından çıkararak işlemci gücünü maksimize eder.

---

## ⚙️ Donanım Uyumluluk Matrisi

Sistem, "Edge AI" prensipleriyle kodlanmış olup, donanım sınırlarını sonuna kadar kullanacak şekilde asenkronize edilmiştir.

| Bileşen | Uç Nokta (Raspberry Pi 5) | C2 Karargah Sistemi |
| :--- | :--- | :--- |
| **CPU** | Cortex-A76 (Optimized) | AMD Ryzen 5 7535HS (3.3 GHz - 4.4GHz Turbo) |
| **GPU / NPU** | XNNPACK / Arm Neon | NVIDIA RTX 2050 4GB GDDR6 (64 bit - CUDA) |
| **RAM / Disk** | 8 GB LPDDR4X | 16 GB DDR5 / 512 GB M2 NVMe SSD |
| **YOLO Modeli**| YOLOv8n (Nano) / INT8 | YOLOv8x (Extra Large) |
| **Performans** | 15-25 FPS (Real-time) | 60-90 FPS (Saf Donanım Optimizasyonu) |
| **Ağ Gecikmesi**| < 45ms | Milisaniye Seviyesi (Event-Driven Stream) |

---

## 🚀 Hızlı Kurulum (Quick Start)

Projenin bağımlılıklarının izole bir sanal ortamda (venv) kurulması tavsiye edilir. İşletim sistemi seviyesindeki grafik ve ses kütüphanelerinin (Garuda/Arch için) yüklü olduğundan emin olun.

```bash
# İşletim sistemi bağımlılıklarını kurun (Arch/Garuda Linux için)
sudo pacman -S tk mpg123

# Projeyi klonla
git clone [https://github.com/DerdliAsiq/OmniVision.git](https://github.com/DerdliAsiq/OmniVision.git)
cd OmniVision

# Sanal ortamı oluştur ve aktif et
python3 -m venv venv
source venv/bin/activate 

# Python bağımlılıklarını yükle
pip install -r requirements.txt

# Ana uygulamayı (ve arka plandaki Web Sunucusunu) ateşle
python main.py
```

📡 C2 Web Terminaline Bağlantı

Uygulama başladığında arka planda FastAPI sunucusu devreye girer.
Aynı ağdaki herhangi bir cihazdan (Telefon/Tablet/PC) şu adrese gidin:
👉 http://localhost:8000 veya http://<BILGISAYAR_IP_ADRESI>:8000
⌨️ Taktiksel Kısayollar (Fiziksel)

    [S] : Hedef Seçim Radarını Aç (Tkinter Arayüzü)

    [A] : Alarm Sistemini Devreye Sok / Devreden Çıkar

    [D] : OmniVision HUD Gizle/Göster

    [T] : ByteTrack Hedef İzleme (Trace) Aç/Kapat

    [H] : Dinamik Ufuk Çizgisi (Horizon Scan) Aç/Kapat

    [Q] : Operasyonu Güvenli Şekilde Sonlandır

📦 Temel Python Bağımlılıkları

    ultralytics: YOLOv8 çekirdeği.

    supervision: Taktiksel çizimler ve ByteTrack izleme motoru.

    fastapi & uvicorn: Asenkron Komuta Kontrol web sunucusu.

    opencv-python: Matris işleme ve donanım hızlandırmalı MJPEG sıkıştırma.

🔓 Lisans (Open Source)

MIT License
Bu yazılım tamamen açık kaynaklıdır ve MIT Lisansı koşulları altında özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir. Daha fazla detay için LICENSE dosyasına bakabilirsiniz.

🛡️ Geliştirici Bilgisi: DerdliAsiq (Project: OmniVision Open Source Initiative)

