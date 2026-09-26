"""
TacticalVision: State-of-the-Art Neural Surveillance & Tactical Analytics Platform

This package provides hardware-aware vision processing and AI-powered object detection
and tracking capabilities designed for security and surveillance applications.
"""

__author__ = "DerdliAsiq"

# Versiyonun tek kaynagi: config.SystemState.VERSION
try:
    from config import SystemState as _SystemState

    __version__ = _SystemState.VERSION
except Exception:
    __version__ = "2.0"