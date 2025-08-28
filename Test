from ultralytics import YOLO
import torch

print("Testing YOLO model loading...")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

# Load YOLOv5 nano model
model = YOLO('yolov5n.pt')
print("YOLO model loaded successfully!")

# Test with dummy input
import numpy as np
dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
results = model(dummy_image)
print(f"Model inference test successful! Detected {len(results[0].boxes)} objects")
