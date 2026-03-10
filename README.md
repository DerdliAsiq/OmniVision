👁️ OmniVision v1.2

State-of-the-Art Neural Surveillance & Tactical Analytics Platform

OmniVision, kritik tesislerin ve operasyonel sahaların otonom gözetlenmesi için geliştirilmiş hibrit bir yapay zeka platformudur. DerdliAsiq tarafından açık kaynak dünyasına kazandırılan bu sistem; düşük gecikmeli nesne takibi, dinamik çevre güvenliği ve donanım hızlandırmalı analiz katmanlarını bir arada sunar.
🛠️ Teknik Mimari ve Özellikler

Sistem, "Edge AI" prensipleriyle tasarlanmış olup modern taktiksel operasyonlar için aşağıdaki çekirdeklerden oluşur:

    Omni-Engine: Donanım farkındalığına (Hardware-Aware) sahip, asenkron görüntü yakalama motoru. Raspberry Pi 5 (V4L2) ve RTX 2050 (CUDA) sistemlerinde otomatik optimizasyon sağlar. Adaptif buffer yönetimi ile frame kaybı minimalize edilmiştir.

    Neural-Shield: YOLOv8 (Nano'dan Extra Large'a kadar ölçeklenebilir) modeli ve supervision kütüphanesi ile donatılmış analiz katmanı. Gerçek zamanlı nesne tespiti ve ByteTrack ile askeri standartlarda (Trace izi bırakan) hedef takibi yapar.

    Horizon Scanner (Ufuk Çizgisi Motoru): İnsansız Deniz Araçları (İDA) ve sallantılı kameralar için dinamik ufuk çizgisi tespiti yapar. Gökyüzünü tarama alanından (ROI) çıkararak işlemci tasarrufu sağlar.

    Tactical Database: Asenkron SQLite veritabanı mimarisi (WAL modu) ve modern web tabanlı (FastAPI) HUD arayüzü ile anlık tehditleri loglar ve geriye dönük istihbarat sunar.

⚙️ Donanım Uyumluluk Matrisi
Bileşen	Raspberry Pi 5 (ARM64)	PC Workstation (x86_64)
CPU	Cortex-A76 (Optimized)	AMD Ryzen 5 7535HS
GPU/NPU	XNNPACK / Arm Neon	NVIDIA RTX 2050 (CUDA)
Model	YOLOv8n (Nano) / INT8	YOLOv8x (Extra Large)
FPS Hedefi	15-25 FPS (Real-time)	30-60+ FPS (Ultra-fast)
Gecikme	< 45ms	< 15ms
🚀 Hızlı Kurulum (Quick Start)

Projenin bağımlılıklarının izole bir sanal ortamda kurulması tavsiye edilir.
Bash

# Projeyi klonla
git clone https://github.com/DerdliAsiq/OmniVision.git
cd OmniVision

# Sanal ortamı oluştur ve aktif et (Linux/Garuda/Ubuntu)
python3 -m venv venv
source venv/bin/activate # Fish shell kullanıyorsanız: source venv/bin/activate.fish

# Bağımlılıkları yükle
pip install -r requirements.txt

# Ana uygulamayı çalıştır
python main.py

📦 Bağımlılıklar

Proje aşağıdaki temel bağımlılıklara ihtiyaç duyar:

    ultralytics: YOLOv8 modelleri ve yapay zeka çekirdeği

    supervision: Gelişmiş taktiksel çizimler, iz bırakma ve alan filtrelemesi

    opencv-python: Görüntü işleme ve ufuk çizgisi tespiti

    torch: CUDA donanım hızlandırması için derin öğrenme altyapısı

    psutil: Gerçek zamanlı sistem performansı (RAM/CPU) izleme

    numpy: Matris ve sayısal işlemler

🔓 Lisans (Open Source)

MIT License

Bu yazılım tamamen açık kaynaklıdır ve MIT Lisansı koşulları altında özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir. Daha fazla detay için LICENSE dosyasına bakabilirsiniz.
🛡️ Geliştirici Bilgisi

    Chief Architect & Developer: DerdliAsiq

    Project: OmniVision Open Source Initiative
