👁️ Aelsa-OmniVision v1.0

    State-of-the-Art Neural Surveillance & Tactical Analytics Platform

Aelsa-OmniVision, kritik tesislerin ve operasyonel sahaların otonom gözetlenmesi için geliştirilmiş hibrit bir yapay zeka platformudur. Berzamin Cyber tarafından geliştirilen sistem; düşük gecikmeli nesne takibi, çevre güvenliği ve donanım hızlandırmalı analiz katmanlarını AELSA Technologies güvencesiyle sunar.
🛠️ Teknik Mimari ve Özellikler

Sistem, "Edge AI" prensipleriyle tasarlanmış olup iki ana çekirdekten oluşur:

    Omni-Engine: Donanım farkındalığına (Hardware-Aware) sahip, asenkron görüntü yakalama motoru. Raspberry Pi 5 (V4L2) ve RTX 2050 (CUDA) sistemlerinde otomatik optimizasyon sağlar.

    Neural-Shield: YOLOv8-Nano ve Supervision entegrasyonu ile donatılmış analiz katmanı. Sektör standardı annotator'lar ile yüksek doğruluklu etiketleme ve izleme gerçekleştirir.

Donanım Uyumluluk Matrisi
Bileşen	Raspberry Pi 5 (ARM64)	PC Workstation (x86_64)
CPU	Cortex-A76 (Optimized)	AMD Ryzen 5 7535HS
GPU/NPU	XNNPACK / Arm Neon	NVIDIA RTX 2050 (CUDA)
FPS Hedefi	15-25 FPS (Real-time)	60+ FPS (Ultra-fast)
Gecikme	< 45ms	< 15ms
🚀 Hızlı Kurulum (Quick Start)

AELSA Defence güvenli geliştirme protokolü gereği, bağımlılıkların izole bir sanal ortamda kurulması zorunludur.
Bash

# Projeyi klonla (Erişim yetkiniz varsa)
git clone https://github.com/AELSA-Technologies/Aelsa-OmniVision.git
cd Aelsa-OmniVision

# Sanal ortamı oluştur ve aktif et (Linux/Kali)
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

🔒 Lisans ve Gizlilik (Proprietary)

AELSA-OMNIVISION TÜM HAKLARI SAKLIDIR.

Bu yazılımın kaynak kodları, mimari şemaları ve eğitim modelleri AELSA Technologies iştiraki olan AELSA Defence birimine aittir.

    Kodun izinsiz kopyalanması, üçüncü şahıslarla paylaşılması veya tersine mühendislik (Reverse Engineering) işlemlerine tabi tutulması kesinlikle yasaktır.

    Yazılım "olduğu gibi" sunulur ve ticari kullanımı sadece yazılı izin ile mümkündür.

🛡️ Geliştirici Bilgisi

Chief Developer: Berzamin Cyber

Advisory: Vigilante Co-Founder AI

Organization: AELSA Technologies / AELSA Defence
