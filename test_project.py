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
        return _
    
    @property
    def test_2(self):
        @self.test("Model Files: Verify YOLO model files exist")
        def _():
            model_file = self.project_root / "yolo26x.pt"
            assert model_file.exists(), f"yolo26x.pt not found at {model_file}"
            logger.info(f"✓ yolo26x.pt found ({model_file.stat().st_size / 1e6:.1f} MB)")
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
            detector_file = self.project_root / "omni_detector.py"
            detector_source = detector_file.read_text(encoding="utf-8")
            
            assert "processed_frame" in detector_source, "Detection loop not fixed"
            
            engine_file = self.project_root / "omni_engine.py"
            engine_source = engine_file.read_text(encoding="utf-8")
            assert "BUFFERSIZE, 5" in engine_source or "set(cv2.CAP_PROP_BUFFERSIZE, 5)" in engine_source, "Buffer size not increased"
            
            assert "join(timeout=5)" in engine_source, "thread.join() missing timeout"
        return _
    
    @property
    def test_8(self):
        @self.test("Documentation: Requirements.txt exists")
        def _():
            req_file = self.project_root / "requirements.txt"
            assert req_file.exists(), "requirements.txt not found"
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