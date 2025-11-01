import cv2
import numpy as np
from ultralytics import YOLO

# Load your trained YOLO model (adjust path if needed)
model = YOLO("l_version_1_214.pt")  # replace with your model filename

def recognize_face_from_frame(frame):
    """
    Takes an image frame (numpy array), detects and recognizes a face,
    and returns the recognized student's name or None.
    """
    results = model(frame, verbose=False)
    for result in results:
        boxes = result.boxes
        if len(boxes) > 0:
            # You can add custom logic here to identify student by face embedding
            # For now, we just return a placeholder name
            # Example: use student_id = boxes.cls[0].item()
            return "Recognized_Student"
    return None
