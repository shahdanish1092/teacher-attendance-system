# face_recognition_helper.py
import cv2
import numpy as np
from ultralytics import YOLO
import os

model = None
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "l_version_1_214.pt")

try:
    if os.path.isfile(MODEL_PATH):
        model = YOLO(MODEL_PATH)
        print("✅ YOLO model loaded:", MODEL_PATH)
    else:
        print("⚠️ YOLO model not found at", MODEL_PATH)
except Exception as e:
    model = None
    print("⚠️ Failed to load YOLO model:", e)


def recognize_face_from_frame(frame):
    """
    Returns recognized student's name or identifier (string) or None.
    This function depends on your trained model and how you map model outputs to student IDs.
    """
    if model is None:
        raise RuntimeError("YOLO model not loaded")

    # Run model (assumes model returns boxes and class/label mapping)
    results = model(frame, verbose=False)
    # Customize the interpretation according to how you trained the model
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes and len(boxes) > 0:
            # This placeholder returns the first detected class name if available
            # Replace with your actual mapping (e.g., boxes.cls or r.names[index])
            try:
                cls_idx = int(boxes.cls[0].item())
                name = r.names.get(cls_idx, f"class_{cls_idx}")
                return name
            except Exception:
                return "Detected"
    return None
