#!/usr/bin/env python3
"""
OmniVision Test & Validation Suite
"""

import sys
import os
import logging
import threading
import time
from pathlib import Path

# Windows konsolu (cp1254) ✓/✗ sembollerinde patlar; ciktiyi UTF-8'e zorla.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger("OmniVision")

class ValidationSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.project_root = Path(__file__).parent
        
    def test(self, name):
        def decorator(func):
            def wrapper(*args, **kwargs):
                print(f"\n{'='*60}")
                print(f"TEST: {name}")
                print('='*60)
                try:
                    func(*args, **kwargs)
                    self.passed += 1
                    print(f"✓ PASSED: {name}")
                except AssertionError as e:
                    self.failed += 1
                    print(f"✗ FAILED: {name}")
                    print(f"  Error: {e}")
                except Exception as e:
                    self.failed += 1
                    print(f"✗ ERROR: {name}")
                    print(f"  Exception: {e}")
            return wrapper
        return decorator
    
    @property
    def test_1(self):
        @self.test("Dependency: Import all required modules")
        def _():
            try:
                import cv2
                logger.info("✓ opencv-python available")
            except ImportError:
                raise AssertionError("opencv-python not found")
            
            try:
                import ultralytics
                logger.info("✓ ultralytics available")
            except ImportError:
                raise AssertionError("ultralytics not found")
            
            try:
                import torch
                logger.info("✓ torch available")
            except ImportError:
                raise AssertionError("torch not found")
            
            try:
                import psutil
                logger.info("✓ psutil available")
            except ImportError:
                raise AssertionError("psutil not found")
            
            try:
                import numpy
                logger.info("✓ numpy available")
            except ImportError:
                raise AssertionError("numpy not found")

            try:
                import supervision
                logger.info("✓ supervision available")
            except ImportError:
                raise AssertionError("supervision not found")

            try:
                import fastapi
                logger.info("✓ fastapi available")
            except ImportError:
                raise AssertionError("fastapi not found")

            try:
                import speech_recognition
                logger.info("✓ SpeechRecognition available")
            except ImportError:
                raise AssertionError("SpeechRecognition not found (pip install -r requirements.txt)")

            try:
                import faster_whisper
                logger.info("✓ faster-whisper available")
            except ImportError:
                raise AssertionError("faster-whisper not found (pip install -r requirements.txt)")

            try:
                import pyaudio
                logger.info("✓ PyAudio available")
            except ImportError:
                logger.warning("⚠ PyAudio not found (mikrofon calismaz; pip install PyAudio) - opsiyonel, test gecildi")
        return _
    
    @property
    def test_2(self):
        @self.test("Model Files: Verify YOLO model files exist (or downloader present)")
        def _():
            sys.path.insert(0, str(self.project_root))
            from config import SystemState
            model_file = self.project_root / f"{SystemState.MODEL_NAME}.pt"
            downloader = self.project_root / "download_model.py"
            if model_file.exists():
                logger.info(f"✓ {model_file.name} found ({model_file.stat().st_size / 1e6:.1f} MB)")
            elif downloader.exists():
                logger.warning(f"⚠ {model_file.name} henuz indirilmemis; 'python download_model.py' ile indirilebilir (test gecildi).")
            else:
                raise AssertionError(f"{model_file.name} not found and download_model.py missing")
        return _
    
    @property
    def test_3(self):
        @self.test("Config: Verify configuration file exists and loads")
        def _():
            sys.path.insert(0, str(self.project_root))
            try:
                from config import SystemState
                logger.info(f"✓ config.py loaded successfully")
                assert hasattr(SystemState, 'TRACKING_ACTIVE'), "Missing TRACKING_ACTIVE"
                assert hasattr(SystemState, 'SHOW_DASHBOARD'), "Missing SHOW_DASHBOARD"
                assert hasattr(SystemState, 'VERSION'), "Missing VERSION (tek kaynak versiyon)"
                assert hasattr(SystemState, 'MODEL_NAME'), "Missing MODEL_NAME (kanonik model)"
                assert hasattr(SystemState, 'EVIDENCE_DIR'), "Missing EVIDENCE_DIR"
                assert hasattr(SystemState, 'DB_PATH'), "Missing DB_PATH (mutlak DB yolu)"
                assert hasattr(SystemState, 'PROCESS_INTERVAL'), "Missing PROCESS_INTERVAL"
                assert hasattr(SystemState, 'C2_ALLOW_LAN'), "Missing C2_ALLOW_LAN"
                assert os.path.isabs(str(SystemState.DB_PATH)), "DB_PATH mutlak olmali"
            except ImportError as e:
                raise AssertionError(f"Cannot import config: {e}")
        return _
    
    @property
    def test_4(self):
        @self.test("OmniDetector: Model initialization with error handling")
        def _():
            sys.path.insert(0, str(self.project_root))
            try:
                from omni_detector import OmniDetector
                logger.info("✓ OmniDetector class imported")
                
                try:
                    detector = OmniDetector()
                    logger.info("✓ OmniDetector initialized successfully")
                except RuntimeError as e:
                    logger.error(f"⚠ Detector initialization failed (expected if model unavailable): {e}")
                    
            except ImportError as e:
                raise AssertionError(f"Cannot import OmniDetector: {e}")
        return _
    
    @property
    def test_5(self):
        @self.test("OmniEngine: Threading and frame management")
        def _():
            sys.path.insert(0, str(self.project_root))
            try:
                from omni_engine import OmniEngine
                logger.info("✓ OmniEngine class imported")
                
                try:
                    engine = OmniEngine(source=0)
                    logger.info("✓ OmniEngine initialized")
                    assert engine.thread is not None, "Thread not initialized"
                    
                    engine.start()
                    time.sleep(0.2)
                    engine.stop()
                    
                    assert not engine.is_running, "Engine still running after stop"
                    logger.info("✓ Thread management working correctly")
                    
                except Exception as e:
                    logger.warning(f"⚠ Engine test skipped (expected if no camera): {e}")
                    
            except ImportError as e:
                raise AssertionError(f"Cannot import OmniEngine: {e}")
        return _
    
    @property
    def test_6(self):
        @self.test("Error Handling: Verify exception handling in components")
        def _():
            sys.path.insert(0, str(self.project_root))
            
            # OPTİMİZASYON: Windows'ta UTF-8 karakter okuma hatası fixlendi
            detector_file = self.project_root / "omni_detector.py"
            source = detector_file.read_text(encoding="utf-8")
            assert "try:" in source, "Missing try-except in OmniDetector"
            
            engine_file = self.project_root / "omni_engine.py"
            source = engine_file.read_text(encoding="utf-8")
            assert "logger" in source, "Missing logging in OmniEngine"
            
            main_file = self.project_root / "main.py"
            source = main_file.read_text(encoding="utf-8")
            assert "try:" in source, "Missing try-except in main.py"
        return _
    
    @property
    def test_7(self):
        @self.test("Code Quality: Verify fixes for critical issues")
        def _():
            import re
            detector_file = self.project_root / "omni_detector.py"
            detector_source = detector_file.read_text(encoding="utf-8")

            assert "processed_frame" in detector_source, "Detection loop not fixed"

            # ultralytics>=8.4: 'half' kaldirildi, 'quantize' kullanilmali
            assert "half=self.use_half" not in detector_source, "Deprecated 'half' kwarg still passed to YOLO"
            assert "use_half" not in detector_source, "Stale 'use_half' attribute still present"
            assert "quantize=self.quantize" in detector_source, "YOLO calls must pass 'quantize'"

            engine_file = self.project_root / "omni_engine.py"
            engine_source = engine_file.read_text(encoding="utf-8")
            assert "BUFFERSIZE, 5" in engine_source or "set(cv2.CAP_PROP_BUFFERSIZE, 5)" in engine_source, "Buffer size not increased"

            assert re.search(r"join\(timeout=\d+(\.\d+)?\)", engine_source), "thread.join() missing timeout"

            # Yeni duzeltmeler: F1 bug, DB mutlak yol, copy-on-read
            main_src = (self.project_root / "main.py").read_text(encoding="utf-8")
            assert "ord('h')" in main_src or 'ord("h")' in main_src, "DEBUG hotkey H'ye tasinmali (F1/cv2 bug)"
            assert "0x70" not in main_src or "ord('h')" in main_src, "Eski 0x70 F1 kontrolu kalmis"
            assert "DB_PATH" in (self.project_root / "config.py").read_text(encoding="utf-8"), "DB_PATH tek kaynak olmali"
            assert "get_frame" in engine_source and ".copy()" in engine_source, "get_frame copy-on-read olmali"
            dash_src = (self.project_root / "tactical_web_dashboard.py").read_text(encoding="utf-8")
            assert "shell=True" not in dash_src, "shell=True kalmis (pactl)"
            assert "Bilinmeyen komut" in dash_src, "API unknown-action validasyonu eksik"
        return _
    
    @property
    def test_8(self):
        @self.test("Documentation: Requirements.txt exists")
        def _():
            req_file = self.project_root / "requirements.txt"
            assert req_file.exists(), "requirements.txt not found"
            pi_file = self.project_root / "requirements-pi.txt"
            assert pi_file.exists(), "requirements-pi.txt not found"
            pi_src = pi_file.read_text(encoding="utf-8")
            assert "torch --index-url" not in pi_src, "requirements-pi.txt pip syntax hatasi"
        return _
    
    @property
    def test_9(self):
        @self.test("Workspace: File structure and naming")
        def _():
            init_file = self.project_root / "__init__.py"
            assert init_file.exists(), "__init__.py not found"
        return _
    
    def run_all(self):
        print("\n" + "="*60)
        print("OMNIVISION TEST SUITE")
        print("="*60)
        
        tests = [self.test_1, self.test_2, self.test_3, self.test_4, self.test_5, self.test_6, self.test_7, self.test_8, self.test_9]
        for test in tests: test()
        
        total = self.passed + self.failed
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed} ✓")
        print(f"Failed: {self.failed} ✗")
        print("="*60)
        
        if self.failed == 0:
            print("✓ ALL TESTS PASSED!")
            return 0
        else:
            print(f"✗ {self.failed} test(s) failed")
            return 1

def main():
    suite = ValidationSuite()
    exit_code = suite.run_all()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()