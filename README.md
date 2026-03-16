# 👁️ OmniVision: Taktiksel C2 Gözetim Platformu

## Web Site

https://omnivision-q8xdmnay.manus.space/

## ✨ Yapay Zeka Destekli Otonom Gözetim ve Komuta Kontrol Merkezi

OmniVision, kritik tesislerin ve operasyonel sahaların otonom gözetlenmesi için geliştirilmiş, son teknoloji hibrit bir yapay zeka platformudur. DerdliAsiq tarafından açık kaynak dünyasına kazandırılan bu sistem; düşük gecikmeli nesne takibi, dinamik çevre güvenliği ve donanım hızlandırmalı analiz katmanlarını bir araya getirerek, gözetim ve güvenlik operasyonlarını yeni bir boyuta taşır.

V1.2 güncellemeleriyle birlikte OmniVision, yerel bir tespit yazılımı olmaktan çıkarak, tam asenkron çalışan **C2 (Command & Control) Web Terminali** ile donatılmış gerçek bir uzaktan komuta merkezine dönüşmüştür. Bu sayede, operasyonel verimlilik ve durumsal farkındalık en üst düzeye çıkarılmıştır.

## 🚀 Öne Çıkan Taktiksel Özellikler

OmniVision, sahadaki zorlu koşullar için özel olarak tasarlanmış bir dizi yenilikçi özellik sunar:

*   **C2 Web Dashboard (Uzaktan Komuta):** FastAPI tabanlı, asenkron `asyncio` motoru ile güçlendirilmiş modern kontrol paneli. Ana yapay zeka döngüsünü (OpenCV) yormadan, sıfır gecikmeli (low-latency) MJPEG canlı video akışı sağlayarak kesintisiz komuta imkanı sunar.
*   **Anti-Sabotaj Ses Protokolü (OS Override):** Garuda Linux (PipeWire/PulseAudio) çekirdeğine doğrudan hükmeden `pactl` entegrasyonu sayesinde, ana makine fiziki olarak sessize alınsa bile uzaktan **MAX SES (OVERRIDE)** komutu ile sistemi %100 güçte tetikleme yeteneği. Bu özellik, sabotaj girişimlerine karşı kritik bir savunma katmanı oluşturur.
*   **Kinetik Flaşör (Target Lock-on):** Radara giren tehditleri izlerken "tünel vizyonunu" önleyen çoklu tarama mimarisi. Seçili hedeflerin üzerine saniyede 6 kez Kırmızı/Siyah çakar (strobe) efekti ve taktiksel nişangah atarak operatörün dikkatini doğrudan merkeze çeker ve hızlı müdahale sağlar.
*   **Dinamik Hedef Seçim Radarı (Tkinter):** 80 farklı COCO sınıfı arasında anlık filtreleme yapabilen, A-Z alfabetik sıralı ve "Demir Hafızalı" (önceki seçimleri unutmayan) taktiksel hedef arayüzü. Bu sayede operatörler, ilgi alanlarına göre hedefleri kolayca belirleyebilir.
*   **Akıllı Ses Kilidi (Smart Audio Lock):** Subprocess tabanlı akıllı alarm motoru. CPU'yu boğan kör döngüler yerine, seslerin üst üste binmesini (%0 overlap) fiziksel olarak engelleyen I/O optimizasyonu ile kesintisiz ve etkili sesli uyarılar sunar.
*   **Horizon Scanner (Ufuk Çizgisi Motoru):** İnsansız Deniz Araçları (İDA) ve stabil olmayan kameralar için dinamik ufuk çizgisi tespiti yapar. Gökyüzünü ROI (Region of Interest) alanından çıkararak işlemci gücünü maksimize eder ve yanlış alarmları minimize eder.

## ⚙️ Donanım Uyumluluk Matrisi

OmniVision, "Edge AI" prensipleriyle kodlanmış olup, donanım sınırlarını sonuna kadar kullanacak şekilde asenkronize edilmiştir. Aşağıdaki matris, sistemin farklı donanım konfigürasyonlarındaki uyumluluğunu ve performansını göstermektedir:

| Bileşen | Uç Nokta (Raspberry Pi 5) | C2 Karargah Sistemi |
| :------ | :------------------------ | :----------------------------------- |
| **CPU** | Cortex-A76 (Optimized)    | AMD Ryzen 5 7535HS (3.3 GHz - 4.4GHz Turbo) |
| **GPU / NPU** | XNNPACK / Arm Neon        | NVIDIA RTX 2050 4GB GDDR6 (64 bit - CUDA) |
| **RAM / Disk** | 8 GB LPDDR4X              | 16 GB DDR5 / 512 GB M2 NVMe SSD      |
| **YOLO Modeli** | YOLOv8n (Nano) / INT8     | YOLOv8x (Extra Large)                |
| **Performans** | 15-25 FPS (Gerçek Zamanlı) | 60-90 FPS (Saf Donanım Optimizasyonu) |
| **Ağ Gecikmesi** | < 45ms                    | Milisaniye Seviyesi (Olay Odaklı Akış) |

## 🚀 Hızlı Kurulum

OmniVision'ı hızlıca kurmak ve çalıştırmak için aşağıdaki adımları takip edin. Projenin bağımlılıklarının izole bir sanal ortamda (venv) kurulması şiddetle tavsiye edilir. İşletim sistemi seviyesindeki grafik ve ses kütüphanelerinin (özellikle Garuda/Arch Linux için) yüklü olduğundan emin olun.

```shell
# İşletim sistemi bağımlılıklarını kurun (Arch/Garuda Linux için)
sudo pacman -S tk mpg123

# Projeyi klonlayın
git clone https://github.com/DerdliAsiq/OmniVision.git
cd OmniVision

# Sanal ortamı oluşturun ve aktif edin
python3 -m venv venv
source venv/bin/activate 

# Python bağımlılıklarını yükleyin
pip install -r requirements.txt

# Ana uygulamayı (ve arka plandaki Web Sunucusunu) başlatın
python main.py
```

## 📡 C2 Web Terminaline Bağlantı

Uygulama başladığında arka planda FastAPI sunucusu otomatik olarak devreye girer. Aynı ağdaki herhangi bir cihazdan (Telefon/Tablet/PC) aşağıdaki adreslere giderek C2 Web Terminaline erişebilirsiniz:

👉 [http://localhost:8000](http://localhost:8000)
👉 `http://<BILGISAYAR_IP_ADRESI>:8000`

## ⌨️ Taktiksel Kısayollar (Fiziksel)

Operasyonel verimliliği artırmak için fiziksel klavye kısayolları:

*   `[S]` : Hedef Seçim Radarını Aç (Tkinter Arayüzü)
*   `[A]` : Alarm Sistemini Devreye Sok / Devreden Çıkar
*   `[D]` : OmniVision HUD Gizle/Göster
*   `[T]` : ByteTrack Hedef İzleme (Trace) Aç/Kapat
*   `[H]` : Dinamik Ufuk Çizgisi (Horizon Scan) Aç/Kapat
*   `[Q]` : Operasyonu Güvenli Şekilde Sonlandır

## 📦 Temel Python Bağımlılıkları

OmniVision'ın temel işlevselliğini sağlayan ana Python kütüphaneleri:

*   `ultralytics`: YOLOv8 çekirdeği için.
*   `supervision`: Taktiksel çizimler ve ByteTrack izleme motoru için.
*   `fastapi` & `uvicorn`: Asenkron Komuta Kontrol web sunucusu için.
*   `opencv-python`: Matris işleme ve donanım hızlandırmalı MJPEG sıkıştırma için.

## 🔓 Lisans

Bu yazılım tamamen açık kaynaklıdır ve **MIT Lisansı** koşulları altında özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir. Daha fazla detay için `LICENSE` dosyasına bakabilirsiniz.

## 🛡️ Geliştirici Bilgisi

**DerdliAsiq** tarafından geliştirilen OmniVision, açık kaynak topluluğuna katkıda bulunmayı hedefleyen bir projedir. Sorularınız veya katkılarınız için lütfen GitHub deposunu ziyaret edin.
