#!/usr/bin/env python3
"""
OmniVision model indirme betigi.
Kanonik model: config.SystemState.MODEL_NAME (tek kaynak).

Kullanim:
    python download_model.py            # kanonik modeli indirir
    python download_model.py yolov8n    # ozel bir modeli indirir

YOLO, ilk OmniDetector baslatmasinda da otomatik indirir; bu betik
ozellikle offline / saha (Raspberry Pi) kurulumlari icin onceden
hazirlik yapmaya yarar.
"""

import sys
from pathlib import Path

from config import SystemState


def download(model_name=None):
    model_name = model_name or SystemState.MODEL_NAME
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[X] ultralytics paketi bulunamadi. Once: pip install -r requirements.txt")
        return 1

    pt_file = Path(f"{model_name}.pt")
    if pt_file.exists():
        print(f"[+] Model zaten mevcut: {pt_file} ({pt_file.stat().st_size / 1e6:.1f} MB)")
        return 0

    print(f"[*] Model indiriliyor: {model_name} ...")
    YOLO(f"{model_name}.pt")  # ultralytics agirligi otomatik indirir
    if pt_file.exists():
        print(f"[+] Indirme tamamlandi: {pt_file} ({pt_file.stat().st_size / 1e6:.1f} MB)")
        return 0
    print("[X] Indirme sonrasi model dosyasi bulunamadi.")
    return 1


if __name__ == "__main__":
    sys.exit(download(sys.argv[1] if len(sys.argv) > 1 else None))
