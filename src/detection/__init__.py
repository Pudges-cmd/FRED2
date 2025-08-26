# src/detection/__init__.py
"""
Detection modules
"""

from .yolo_detector import YOLODetector
from .camera_handler import CameraHandler

__all__ = ['YOLODetector', 'CameraHandler']