#!/usr/bin/env python3
"""
Simple Human Detection Test for Raspberry Pi Zero 2W
Uses YOLOv5n with PiCamera2 for real-time human detection
"""

import cv2
import time
import numpy as np
from picamera2 import Picamera2
from ultralytics import YOLO
from datetime import datetime
import os

class SimpleHumanDetector:
    def __init__(self):
        print("Initializing Human Detector...")
        
        # Initialize camera
        self.picam2 = Picamera2()
        self.picam2.configure(self.picam2.create_preview_configuration(
            main={"format": 'XRGB8888', "size": (640, 480)}
        ))
        
        # Load YOLO model
        print("Loading YOLO model...")
        self.model = YOLO('yolov5n.pt')
        
        # Human class ID in COCO dataset
        self.human_class_id = 0
        
        # Detection parameters
        self.confidence_threshold = 0.5
        
        # Logging
        self.log_file = "human_detections.txt"
        
        print("Human Detector initialized successfully!")
    
    def start_camera(self):
        """Start camera capture"""
        self.picam2.start()
        time.sleep(2)  # Camera warm-up
    
    def stop_camera(self):
        """Stop camera capture"""
        self.picam2.stop()
    
    def detect_humans(self, frame):
        """Detect humans in frame"""
        # Run YOLO inference
        results = self.model(frame, verbose=False)
        
        human_count = 0
        human_boxes = []
        
        # Process results
        if results[0].boxes is not None:
            for box in results[0].boxes:
                # Check if detection is human and above confidence threshold
                if (int(box.cls[0]) == self.human_class_id and 
                    float(box.conf[0]) >= self.confidence_threshold):
                    human_count += 1
                    
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    confidence = float(box.conf[0])
                    human_boxes.append((x1, y1, x2, y2, confidence))
        
        return human_count, human_boxes
    
    def draw_detections(self, frame, boxes):
        """Draw bounding boxes on frame"""
        for x1, y1, x2, y2, conf in boxes:
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"Human: {conf:.2f}"
            cv2.putText(frame, label, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return frame
    
    def log_detection(self, count, timestamp):
        """Log detection to file"""
        log_entry = f"{timestamp}: {count} humans detected\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
        
        print(f"Logged: {log_entry.strip()}")
    
    def run_detection_loop(self, duration=300):  # Run for 5 minutes by default
        """Main detection loop"""
        print(f"Starting human detection for {duration} seconds...")
        print("Press Ctrl+C to stop early")
        
        self.start_camera()
        
        start_time = time.time()
        frame_count = 0
        total_detections = 0
        
        try:
            while (time.time() - start_time) < duration:
                # Capture frame
                frame = self.picam2.capture_array()
                frame_count += 1
                
                # Convert XRGB to RGB for YOLO
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_XRGB2RGB)
                
                # Detect humans
                human_count, boxes = self.detect_humans(frame_rgb)
                
                if human_count > 0:
                    total_detections += human_count
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f"🚨 DETECTION ALERT: {human_count} humans detected at {timestamp}")
                    self.log_detection(human_count, timestamp)
                    
                    # Draw detections (for debugging)
                    frame_with_boxes = self.draw_detections(frame_rgb, boxes)
                    
                    # Optional: Save detection image
                    detection_filename = f"detection_{timestamp.replace(':', '-').replace(' ', '_')}.jpg"
                    cv2.imwrite(detection_filename, cv2.cvtColor(frame_with_boxes, cv2.COLOR_RGB2BGR))
                    print(f"Saved detection image: {detection_filename}")
                
                # Print status every 30 seconds
                if frame_count % (30 * 15) == 0:  # 15 FPS assumption
                    elapsed = time.time() - start_time
                    print(f"Status: {elapsed:.0f}s elapsed, {total_detections} total detections")
                
                # Small delay to prevent overheating
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n👋 Detection stopped by user")
        
        finally:
            self.stop_camera()
            
            # Final statistics
            elapsed = time.time() - start_time
            print(f"\n📊 Detection Summary:")
            print(f"Duration: {elapsed:.1f} seconds")
            print(f"Frames processed: {frame_count}")
            print(f"Total human detections: {total_detections}")
            print(f"Average FPS: {frame_count/elapsed:.1f}")

if __name__ == "__main__":
    detector = SimpleHumanDetector()
    detector.run_detection_loop(300)  # Run for 5 minutes


chmod +x simple_human_detection.py
