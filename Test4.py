cat > simple_human_detection_2025.py << 'EOF'
#!/usr/bin/env python3
"""
UPDATED Simple Human Detection for Raspberry Pi Zero 2W (2025)
Handles multiple camera backends and libcamera issues
"""

import cv2
import time
import numpy as np
import subprocess
import os
from ultralytics import YOLO
from datetime import datetime

class RobustHumanDetector:
    def __init__(self):
        print("🚀 Initializing ROBUST Human Detector for 2025...")
        
        # Load YOLO model first
        print("📥 Loading YOLO model...")
        self.model = YOLO('yolov5n.pt')
        
        # Human class ID in COCO dataset
        self.human_class_id = 0
        self.confidence_threshold = 0.5
        self.log_file = "human_detections_2025.txt"
        
        # Initialize camera
        self.camera = None
        self.camera_type = None
        self._setup_camera()
        
        print("✅ Human Detector initialized!")
    
    def _setup_camera(self):
        """Try multiple camera backends"""
        print("🔍 Setting up camera with multiple fallback options...")
        
        # Method 1: Try PiCamera2 (preferred for 2025)
        if self._try_picamera2():
            return
        
        # Method 2: Try OpenCV with different indices
        if self._try_opencv_camera():
            return
        
        # Method 3: Try libcamera command capture
        if self._try_libcamera_command():
            return
        
        raise RuntimeError("❌ No working camera backend found!")
    
    def _try_picamera2(self):
        """Try PiCamera2 library"""
        try:
            from picamera2 import Picamera2
            
            print("🔧 Trying PiCamera2...")
            self.camera = Picamera2()
            
            # Try different configurations
            configs = [
                {"main": {"size": (640, 480), "format": "RGB888"}},
                {"main": {"size": (640, 480)}},
                {"main": {"size": (320, 240), "format": "RGB888"}},
            ]
            
            for config in configs:
                try:
                    camera_config = self.camera.create_still_configuration(**config)
                    self.camera.configure(camera_config)
                    self.camera.start()
                    time.sleep(1)
                    
                    # Test capture
                    frame = self.camera.capture_array()
                    if frame is not None and frame.size > 0:
                        print("✅ PiCamera2 working!")
                        self.camera_type = "picamera2"
                        return True
                        
                except Exception as e:
                    print(f"⚠️ PiCamera2 config failed: {e}")
                    continue
                    
        except ImportError:
            print("⚠️ PiCamera2 not available")
        except Exception as e:
            print(f"⚠️ PiCamera2 setup failed: {e}")
        
        return False
    
    def _try_opencv_camera(self):
        """Try OpenCV camera backends"""
        print("🔧 Trying OpenCV camera...")
        
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        
        for backend in backends:
            for camera_id in range(4):  # Try camera IDs 0-3
                try:
                    cap = cv2.VideoCapture(camera_id, backend)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            print(f"✅ OpenCV camera {camera_id} working!")
                            self.camera = cap
                            self.camera_type = "opencv"
                            return True
                        cap.release()
                        
                except Exception as e:
                    continue
        
        print("⚠️ OpenCV camera failed")
        return False
    
    def _try_libcamera_command(self):
        """Try libcamera command line capture"""
        print("🔧 Trying libcamera command capture...")
        
        commands = ['libcamera-still', 'rpicam-still']
        
        for cmd in commands:
            try:
                result = subprocess.run([cmd, '-o', 'test_libcam.jpg', '--timeout', '1'], 
                                      capture_output=True, timeout=5)
                if result.returncode == 0 and os.path.exists('test_libcam.jpg'):
                    print(f"✅ {cmd} working!")
                    self.camera_type = "libcamera_command"
                    self.libcamera_cmd = cmd
                    return True
            except:
                continue
        
        print("⚠️ libcamera command failed")
        return False
    
    def capture_frame(self):
        """Capture frame using available camera method"""
        if self.camera_type == "picamera2":
            return self.camera.capture_array()
        
        elif self.camera_type == "opencv":
            ret, frame = self.camera.read()
            return frame if ret else None
        
        elif self.camera_type == "libcamera_command":
            filename = f"temp_capture_{int(time.time())}.jpg"
            try:
                subprocess.run([self.libcamera_cmd, '-o', filename, '--timeout', '1'], 
                             capture_output=True, timeout=3)
                if os.path.exists(filename):
                    frame = cv2.imread(filename)
                    os.remove(filename)
                    return frame
            except:
                pass
            return None
        
        return None
    
    def detect_humans(self, frame):
        """Detect humans in frame"""
        if frame is None:
            return 0, []
        
        # Ensure frame is in correct format
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # Convert BGR to RGB for YOLO
            if self.camera_type == "opencv":
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
        else:
            return 0, []
        
        # Run YOLO inference
        try:
            results = self.model(frame_rgb, verbose=False)
            
            human_count = 0
            human_boxes = []
            
            # Process results
            if results[0].boxes is not None:
                for box in results[0].boxes:
                    if (int(box.cls[0]) == self.human_class_id and 
                        float(box.conf[0]) >= self.confidence_threshold):
                        human_count += 1
                        
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        confidence = float(box.conf[0])
                        human_boxes.append((x1, y1, x2, y2, confidence))
            
            return human_count, human_boxes
            
        except Exception as e:
            print(f"⚠️ Detection error: {e}")
            return 0, []
    
    def log_detection(self, count, timestamp):
        """Log detection to file"""
        log_entry = f"{timestamp}: {count} humans detected (Camera: {self.camera_type})\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
        
        print(f"📝 {log_entry.strip()}")
    
    def run_detection_loop(self, duration=300):
        """Main detection loop"""
        print(f"🔍 Starting human detection for {duration} seconds...")
        print(f"📹 Using camera type: {self.camera_type}")
        print("⏹️ Press Ctrl+C to stop early")
        
        start_time = time.time()
        frame_count = 0
        total_detections = 0
        
        try:
            while (time.time() - start_time) < duration:
                # Capture frame
                frame = self.capture_frame()
                
                if frame is not None:
                    frame_count += 1
                    
                    # Detect humans
                    human_count, boxes = self.detect_humans(frame)
                    
                    if human_count > 0:
                        total_detections += human_count
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        print(f"🚨 DETECTION: {human_count} humans at {timestamp}")
                        self.log_detection(human_count, timestamp)
                        
                        # Save detection image
                        if self.camera_type != "libcamera_command":
                            detection_filename = f"detection_{timestamp.replace(':', '-').replace(' ', '_')}.jpg"
                            if self.camera_type == "picamera2":
                                cv2.imwrite(detection_filename, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                            else:
                                cv2.imwrite(detection_filename, frame)
                            print(f"💾 Saved: {detection_filename}")
                
                # Status update every 60 seconds
                if frame_count > 0 and frame_count % 60 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"📊 Status: {elapsed:.0f}s | {total_detections} detections | {fps:.1f} fps")
                
                # Prevent overheating
                time.sleep(0.2)
                
        except KeyboardInterrupt:
            print("\n👋 Detection stopped by user")
        
        finally:
            if self.camera_type == "opencv" and self.camera:
                self.camera.release()
            elif self.camera_type == "picamera2" and self.camera:
                self.camera.stop()
            
            # Final statistics
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            
            print(f"\n📊 Final Results:")
            print(f"Duration: {elapsed:.1f} seconds")
            print(f"Frames: {frame_count}")
            print(f"Detections: {total_detections}")
            print(f"Avg FPS: {fps:.1f}")
            print(f"Camera: {self.camera_type}")

if __name__ == "__main__":
    try:
        detector = RobustHumanDetector()
        detector.run_detection_loop(300)  # Run for 5 minutes
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        print("🔧 Try installing missing packages:")
        print("sudo apt install python3-picamera2 libcamera-apps")
