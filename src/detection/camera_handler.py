"""
Camera handler for Raspberry Pi Camera Module V2
Handles camera initialization, frame capture, and cleanup
"""

import cv2
import numpy as np
import logging
import time
import threading
from pathlib import Path

class CameraHandler:
    def __init__(self, resolution=(640, 480), framerate=30, camera_index=0):
        """
        Initialize camera handler
        
        Args:
            resolution (tuple): Camera resolution (width, height)
            framerate (int): Target framerate
            camera_index (int): Camera device index
        """
        self.resolution = resolution
        self.framerate = framerate
        self.camera_index = camera_index
        self.logger = logging.getLogger(__name__)
        
        self.cap = None
        self.is_recording = False
        self.frame_buffer = None
        self.buffer_lock = threading.Lock()
        self.capture_thread = None
        
        self.initialize_camera()
        
    def initialize_camera(self):
        """Initialize camera connection"""
        try:
            self.logger.info(f"Initializing camera {self.camera_index}")
            
            # Try different backends for Raspberry Pi
            backends = [
                cv2.CAP_V4L2,      # Video4Linux2 (preferred for RPi)
                cv2.CAP_GSTREAMER, # GStreamer
                cv2.CAP_ANY        # Any available backend
            ]
            
            for backend in backends:
                try:
                    self.cap = cv2.VideoCapture(self.camera_index, backend)
                    if self.cap.isOpened():
                        self.logger.info(f"Camera opened with backend: {backend}")
                        break
                    else:
                        self.cap.release()
                        self.cap = None
                except:
                    continue
            
            if self.cap is None or not self.cap.isOpened():
                raise Exception("Could not open camera with any backend")
            
            # Configure camera settings
            self.configure_camera()
            
            # Test capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise Exception("Camera test capture failed")
            
            self.logger.info(f"Camera initialized: {self.resolution[0]}x{self.resolution[1]} @ {self.framerate}fps")
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            raise
    
    def configure_camera(self):
        """Configure camera parameters"""
        if not self.cap:
            return
            
        try:
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            # Set framerate
            self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
            
            # Set format (MJPG for better performance)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            
            # Buffer settings (reduce latency)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Auto exposure and white balance
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Enable auto exposure
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)           # Enable auto white balance
            
            # Additional Pi Camera specific settings
            try:
                # Brightness, contrast, saturation (0-100)
                self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 50)
                self.cap.set(cv2.CAP_PROP_CONTRAST, 50)
                self.cap.set(cv2.CAP_PROP_SATURATION, 50)
            except:
                self.logger.debug("Could not set brightness/contrast settings")
            
            # Verify settings
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.logger.info(f"Camera configured: {actual_width}x{actual_height} @ {actual_fps}fps")
            
        except Exception as e:
            self.logger.warning(f"Camera configuration error: {e}")
    
    def start_continuous_capture(self):
        """Start continuous frame capture in background thread"""
        if self.capture_thread and self.capture_thread.is_alive():
            self.logger.warning("Capture thread already running")
            return
            
        self.is_recording = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Started continuous capture")
    
    def stop_continuous_capture(self):
        """Stop continuous frame capture"""
        self.is_recording = False
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5.0)
        self.logger.info("Stopped continuous capture")
    
    def _capture_loop(self):
        """Background thread for continuous frame capture"""
        while self.is_recording and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.buffer_lock:
                        self.frame_buffer = frame.copy()
                else:
                    self.logger.warning("Failed to capture frame in background thread")
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)
    
    def capture_frame(self):
        """
        Capture a single frame
        
        Returns:
            np.array: Captured frame or None if failed
        """
        if not self.is_available():
            self.logger.error("Camera not available")
            return None
            
        try:
            # If continuous capture is running, get frame from buffer
            if self.is_recording and self.frame_buffer is not None:
                with self.buffer_lock:
                    return self.frame_buffer.copy()
            
            # Otherwise capture directly
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame
            else:
                self.logger.warning("Frame capture failed")
                return None
                
        except Exception as e:
            self.logger.error(f"Frame capture error: {e}")
            return None
    
    def capture_multiple_frames(self, count=5, delay=0.1):
        """
        Capture multiple frames and return the best one
        
        Args:
            count (int): Number of frames to capture
            delay (float): Delay between captures
            
        Returns:
            np.array: Best frame based on sharpness
        """
        frames = []
        
        for i in range(count):
            frame = self.capture_frame()
            if frame is not None:
                frames.append(frame)
            if delay > 0:
                time.sleep(delay)
        
        if not frames:
            return None
        
        # Return frame with highest sharpness (Laplacian variance)
        best_frame = None
        best_sharpness = -1
        
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if sharpness > best_sharpness:
                best_sharpness = sharpness
                best_frame = frame
        
        return best_frame