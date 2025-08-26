"""
YOLO-based object detection handler
Supports YOLOv5, YOLOv8, and YOLO11 models
"""

import torch
import cv2
import numpy as np
import logging
from pathlib import Path

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logging.warning("Ultralytics not available, falling back to torch hub")

class YOLODetector:
    def __init__(self, model_path='models/yolov5n.pt', confidence=0.5, target_classes=None):
        """
        Initialize YOLO detector
        
        Args:
            model_path (str): Path to YOLO model file
            confidence (float): Confidence threshold for detections
            target_classes (list): Classes to detect ['person', 'cat', 'dog']
        """
        self.model_path = model_path
        self.confidence = confidence
        self.target_classes = target_classes or ['person', 'cat', 'dog']
        self.logger = logging.getLogger(__name__)
        
        # Map COCO class IDs to target classes
        self.class_mapping = {
            0: 'person',    # person
            15: 'cat',      # cat
            16: 'dog'       # dog
        }
        
        # Reverse mapping for filtering
        self.target_class_ids = [k for k, v in self.class_mapping.items() if v in self.target_classes]
        
        self.model = None
        self.device = self._get_device()
        self.load_model()
        
    def _get_device(self):
        """Determine best available device"""
        if torch.cuda.is_available():
            device = 'cuda'
        else:
            device = 'cpu'
        self.logger.info(f"Using device: {device}")
        return device
        
    def load_model(self):
        """Load YOLO model"""
        try:
            model_path = Path(self.model_path)
            
            if ULTRALYTICS_AVAILABLE:
                # Use Ultralytics YOLO (YOLOv8/YOLO11)
                if model_path.exists():
                    self.logger.info(f"Loading model from {model_path}")
                    self.model = YOLO(str(model_path))
                else:
                    # Download model if not exists
                    model_name = model_path.name
                    self.logger.info(f"Downloading model: {model_name}")
                    self.model = YOLO(model_name)
                    
                # Move to device
                self.model.to(self.device)
                
            else:
                # Fallback to torch hub for YOLOv5
                self.logger.info("Using torch hub YOLOv5")
                self.model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
                self.model.to(self.device)
                self.model.conf = self.confidence
                
            self.logger.info("Model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise
    
    def detect(self, frame):
        """
        Run detection on frame and return filtered results
        
        Args:
            frame (np.array): Input image frame
            
        Returns:
            list: List of detection dictionaries
        """
        if self.model is None:
            self.logger.error("Model not loaded")
            return []
            
        try:
            detections = []
            
            if ULTRALYTICS_AVAILABLE:
                # Ultralytics YOLO inference
                results = self.model(frame, conf=self.confidence, verbose=False)
                
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            class_id = int(box.cls[0])
                            confidence = float(box.conf[0])
                            
                            # Filter for target classes
                            if class_id in self.class_mapping:
                                class_name = self.class_mapping[class_id]
                                if class_name in self.target_classes:
                                    # Get bounding box coordinates
                                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                                    
                                    detections.append({
                                        'class': class_name,
                                        'class_id': class_id,
                                        'confidence': confidence,
                                        'bbox': [x1, y1, x2, y2],
                                        'center': [(x1 + x2) / 2, (y1 + y2) / 2],
                                        'area': (x2 - x1) * (y2 - y1)
                                    })
            else:
                # Torch hub YOLOv5 inference
                results = self.model(frame)
                df = results.pandas().xyxy[0]
                
                for _, row in df.iterrows():
                    class_id = int(row['class'])
                    confidence = float(row['confidence'])
                    
                    if class_id in self.class_mapping and confidence >= self.confidence:
                        class_name = self.class_mapping[class_id]
                        if class_name in self.target_classes:
                            x1, y1, x2, y2 = row['xmin'], row['ymin'], row['xmax'], row['ymax']
                            
                            detections.append({
                                'class': class_name,
                                'class_id': class_id,
                                'confidence': confidence,
                                'bbox': [x1, y1, x2, y2],
                                'center': [(x1 + x2) / 2, (y1 + y2) / 2],
                                'area': (x2 - x1) * (y2 - y1)
                            })
            
            if detections:
                self.logger.debug(f"Detected {len(detections)} objects")
                
            return detections
            
        except Exception as e:
            self.logger.error(f"Detection error: {e}")
            return []
    
    def draw_detections(self, frame, detections):
        """
        Draw detection boxes and labels on frame
        
        Args:
            frame (np.array): Input image frame
            detections (list): List of detections
            
        Returns:
            np.array: Frame with drawn detections
        """
        if not detections:
            return frame
            
        # Colors for different classes
        colors = {
            'person': (0, 255, 0),  # Green
            'cat': (255, 0, 0),     # Blue
            'dog': (0, 0, 255)      # Red
        }
        
        annotated_frame = frame.copy()
        
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection['bbox'])
            class_name = detection['class']
            confidence = detection['confidence']
            color = colors.get(class_name, (255, 255, 255))
            
            # Draw bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            
            # Background for text
            cv2.rectangle(annotated_frame, 
                         (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), 
                         color, -1)
            
            # Text
            cv2.putText(annotated_frame, label, 
                       (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                       (255, 255, 255), 2)
        
        return annotated_frame
    
    def get_detection_stats(self, detections):
        """
        Get statistics about detections
        
        Args:
            detections (list): List of detections
            
        Returns:
            dict: Statistics dictionary
        """
        if not detections:
            return {'total': 0, 'by_class': {}, 'avg_confidence': 0}
            
        stats = {
            'total': len(detections),
            'by_class': {},
            'avg_confidence': sum(d['confidence'] for d in detections) / len(detections),
            'max_confidence': max(d['confidence'] for d in detections),
            'min_confidence': min(d['confidence'] for d in detections)
        }
        
        # Count by class
        for detection in detections:
            class_name = detection['class']
            if class_name not in stats['by_class']:
                stats['by_class'][class_name] = 0
            stats['by_class'][class_name] += 1
            
        return stats
    
    def update_model(self, new_model_path):
        """
        Update model with new weights
        
        Args:
            new_model_path (str): Path to new model file
        """
        try:
            self.logger.info(f"Updating model to {new_model_path}")
            self.model_path = new_model_path
            self.load_model()
            self.logger.info("Model updated successfully")
        except Exception as e:
            self.logger.error(f"Model update failed: {e}")
            raise
    
    def set_confidence(self, confidence):
        """
        Update confidence threshold
        
        Args:
            confidence (float): New confidence threshold
        """
        self.confidence = max(0.1, min(1.0, confidence))  # Clamp between 0.1 and 1.0
        self.logger.info(f"Confidence threshold updated to {self.confidence}")
        
        if hasattr(self.model, 'conf'):
            self.model.conf = self.confidence
    
    def get_model_info(self):
        """Get information about loaded model"""
        if self.model is None:
            return {"status": "not_loaded"}
            
        info = {
            "model_path": self.model_path,
            "confidence": self.confidence,
            "target_classes": self.target_classes,
            "device": self.device,
            "ultralytics_available": ULTRALYTICS_AVAILABLE
        }
        
        return info