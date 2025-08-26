#!/usr/bin/env python3
"""
Disaster Response Detection System
Main entry point
"""

import os
import sys
import json
import logging
import signal
import time
from pathlib import Path
from datetime import datetime

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection.yolo_detector import YOLODetector
from detection.camera_handler import CameraHandler
from communication.gps_handler import GPSHandler
from communication.sms_handler import SMSHandler
from communication.firebase_sync import FirebaseSync
from utils.logger import setup_logging
from utils.config_manager import ConfigManager

class DisasterDetectionSystem:
    def __init__(self):
        self.config = ConfigManager()
        self.logger = setup_logging(self.config.get('logging', {}))
        self.running = True
        self.setup_signal_handlers()
        self.setup_components()
        self.last_alert_time = 0
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        
    def setup_components(self):
        """Initialize all system components"""
        try:
            # Initialize camera
            camera_config = self.config.get('detection', {})
            self.camera = CameraHandler(
                resolution=tuple(camera_config.get('camera_resolution', [640, 480]))
            )
            
            # Initialize detector
            self.detector = YOLODetector(
                model_path=camera_config.get('model_path', 'models/yolov5n.pt'),
                confidence=camera_config.get('confidence_threshold', 0.5),
                target_classes=camera_config.get('target_classes', ['person', 'cat', 'dog'])
            )
            
            # Initialize communication components
            comm_config = self.config.get('communication', {})
            self.gps = GPSHandler(
                port=comm_config.get('serial_port', '/dev/ttyUSB2'),
                baudrate=comm_config.get('serial_baudrate', 115200),
                timeout=comm_config.get('gps_timeout', 30)
            )
            
            self.sms = SMSHandler(
                port=comm_config.get('serial_port', '/dev/ttyUSB2'),
                baudrate=comm_config.get('serial_baudrate', 115200)
            )
            
            # Initialize Firebase if enabled
            firebase_config = self.config.get('firebase', {})
            if firebase_config.get('enabled', False):
                self.firebase = FirebaseSync(firebase_config)
            else:
                self.firebase = None
                
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            raise
    
    def detect_and_alert(self):
        """Main detection and alert logic"""
        try:
            # Capture frame
            frame = self.camera.capture_frame()
            if frame is None:
                return
            
            # Run detection
            detections = self.detector.detect(frame)
            
            if detections:
                # Count detections by class
                counts = self.count_detections(detections)
                total_detected = sum(counts.values())
                
                self.logger.info(f"Detected: {counts} (Total: {total_detected})")
                
                # Get GPS coordinates
                gps_coords = self.gps.get_coordinates()
                
                # Create detection record
                detection_record = {
                    'timestamp': datetime.now().isoformat(),
                    'counts': counts,
                    'gps_coordinates': gps_coords,
                    'total_detected': total_detected,
                    'confidence_scores': [det['confidence'] for det in detections]
                }
                
                # Log detection locally
                self.log_detection(detection_record)
                
                # Send alert if cooldown period has passed
                current_time = time.time()
                cooldown = self.config.get('communication', {}).get('sms_cooldown', 300)
                
                if current_time - self.last_alert_time > cooldown:
                    self.send_alert(detection_record)
                    self.last_alert_time = current_time
                else:
                    remaining = int(cooldown - (current_time - self.last_alert_time))
                    self.logger.info(f"SMS cooldown active, {remaining}s remaining")
                
                # Sync to Firebase if enabled
                if self.firebase:
                    try:
                        self.firebase.upload_detection(detection_record)
                    except Exception as e:
                        self.logger.error(f"Firebase sync failed: {e}")
                        
        except Exception as e:
            self.logger.error(f"Detection cycle error: {e}")
    
    def count_detections(self, detections):
        """Count detections by class"""
        counts = {'person': 0, 'cat': 0, 'dog': 0}
        for detection in detections:
            class_name = detection['class']
            if class_name in counts:
                counts[class_name] += 1
        return counts
    
    def log_detection(self, record):
        """Log detection to local file"""
        log_config = self.config.get('logging', {})
        log_file = Path(log_config.get('detection_log', 'logs/detections.txt'))
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(log_file, 'a') as f:
                f.write(f"{json.dumps(record)}\n")
        except Exception as e:
            self.logger.error(f"Failed to log detection: {e}")
    
    def send_alert(self, detection_record):
        """Send SMS alert to emergency contacts"""
        try:
            counts = detection_record['counts']
            coords = detection_record['gps_coordinates']
            
            # Format alert message
            message = self.format_alert_message(counts, coords)
            
            # Send to all emergency contacts
            contacts = self.config.get('communication', {}).get('emergency_contacts', [])
            
            if not contacts:
                self.logger.warning("No emergency contacts configured")
                return
            
            for contact in contacts:
                try:
                    success = self.sms.send_message(contact, message)
                    if success:
                        self.logger.info(f"Alert sent successfully to {contact}")
                    else:
                        self.logger.error(f"Failed to send SMS to {contact}")
                except Exception as e:
                    self.logger.error(f"SMS send error for {contact}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Alert sending failed: {e}")
    
    def format_alert_message(self, counts, coords):
        """Format emergency alert message"""
        people_count = counts.get('person', 0)
        cat_count = counts.get('cat', 0)
        dog_count = counts.get('dog', 0)
        
        message = "🚨 DISASTER RESPONSE ALERT 🚨\n"
        
        # Detection counts
        detection_parts = []
        if people_count > 0:
            detection_parts.append(f"{people_count} people")
        if cat_count > 0:
            detection_parts.append(f"{cat_count} cats")
        if dog_count > 0:
            detection_parts.append(f"{dog_count} dogs")
            
        if detection_parts:
            message += f"Detected: {', '.join(detection_parts)}\n"
        
        # GPS coordinates
        if coords:
            message += f"Location: {coords['lat']:.6f}, {coords['lon']:.6f}\n"
            message += f"Google Maps: https://maps.google.com/?q={coords['lat']},{coords['lon']}\n"
        else:
            message += "Location: GPS unavailable\n"
        
        # Evacuation site
        evacuation_sites = self.config.get('evacuation_sites', {})
        primary_site = evacuation_sites.get('primary', {})
        
        if primary_site:
            message += f"Evacuate to: {primary_site.get('name', 'Unknown')}\n"
            message += f"Address: {primary_site.get('address', 'Address unavailable')}\n"
        
        # Timestamp
        message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def health_check(self):
        """Perform system health check"""
        try:
            # Check camera
            if not self.camera.is_available():
                self.logger.warning("Camera not available")
                return False
                
            # Check GPS module
            if not self.gps.test_connection():
                self.logger.warning("GPS module not responding")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def run(self):
        """Main execution loop"""
        self.logger.info("🚀 Starting Disaster Detection System")
        self.logger.info(f"Detection interval: {self.config.get('detection', {}).get('detection_interval', 2.0)}s")
        self.logger.info(f"SMS cooldown: {self.config.get('communication', {}).get('sms_cooldown', 300)}s")
        
        detection_interval = self.config.get('detection', {}).get('detection_interval', 2.0)
        health_check_interval = self.config.get('system', {}).get('health_check_interval', 60)
        last_health_check = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # Perform periodic health check
                if current_time - last_health_check > health_check_interval:
                    self.health_check()
                    last_health_check = current_time
                
                # Main detection cycle
                self.detect_and_alert()
                
                # Sleep for detection interval
                time.sleep(detection_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"System error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up system resources"""
        self.logger.info("🛑 Shutting down system...")
        
        try:
            if hasattr(self, 'camera'):
                self.camera.cleanup()
            if hasattr(self, 'gps') and self.gps.serial_conn:
                self.gps.serial_conn.close()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
            
        self.logger.info("✅ System shutdown complete")

def main():
    """Main entry point"""
    try:
        system = DisasterDetectionSystem()
        system.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()