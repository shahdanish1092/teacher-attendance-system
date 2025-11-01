# attendance_system.py
import os
import cv2
import face_recognition
import numpy as np
from datetime import datetime
from supabase_config import supabase

# Path where student reference images are stored (commit these to repo)
STUDENT_IMAGES_DIR = os.path.join("static", "student_images")

# In-memory lists of known encodings and corresponding student ids
_known_encodings = []
_known_ids = []
_initialized = False

def initialize():
    """
    Load all images from STUDENT_IMAGES_DIR and compute face encodings.
    Call this once at app startup.
    """
    global _initialized, _known_encodings, _known_ids
    if _initialized:
        return

    _known_encodings = []
    _known_ids = []
    if not os.path.isdir(STUDENT_IMAGES_DIR):
        print(f"⚠️ Student images directory not found: {STUDENT_IMAGES_DIR}")
        _initialized = True
        return

    files = sorted(os.listdir(STUDENT_IMAGES_DIR))
    print(f"Loading student images from {STUDENT_IMAGES_DIR} ({len(files)} files)...")
    for fname in files:
        if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        sid = os.path.splitext(fname)[0]
        path = os.path.join(STUDENT_IMAGES_DIR, fname)
        try:
            img = face_recognition.load_image_file(path)
            encs = face_recognition.face_encodings(img)
            if encs:
                _known_encodings.append(encs[0])
                _known_ids.append(sid)
                print(f"  - Loaded {sid}")
            else:
                print(f"  - No face found in {fname}, skipping")
        except Exception as e:
            print(f"  - Error loading {fname}: {e}")

    print(f"✅ Loaded {_known_ids.__len__()} student encodings")
    _initialized = True

def _numpy_bgr_from_bytes(img_bytes):
    # decode bytes (jpeg/png) to BGR numpy array
    nparr = np.frombuffer(img_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return bgr

def recognize_face_from_bytes(img_bytes, tolerance=0.5):
    """
    Accepts image bytes (as received from browser), returns matched student_id or None.
    """
    if not _initialized:
        initialize()

    try:
        bgr = _numpy_bgr_from_bytes(img_bytes)
        # convert to RGB for face_recognition
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        face_locs = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, face_locs)

        if not encodings:
            return None

        # For each face found, try to find best match (we will return first match)
        for enc in encodings:
            dists = face_recognition.face_distance(_known_encodings, enc) if _known_encodings else []
            if len(dists) == 0:
                continue
            best_idx = int(np.argmin(dists))
            if dists[best_idx] <= tolerance:
                return _known_ids[best_idx]
        return None
    except Exception as e:
        print("recognize_face error:", e)
        return None

def mark_attendance(student_id, teacher_username=None, subject=None):
    """
    Call Supabase RPC increment_attendance and also write attendance_logs.
    """
    try:
        # 1) Insert attendance log
        supabase.table("attendance_logs").insert({
            "student_id": student_id,
            "teacher": teacher_username or "",
            "subject": subject or ""
        }).execute()

        # 2) Call RPC to increment total_attendance safely
        supabase.rpc("increment_attendance", {"student_id_input": student_id}).execute()
        print(f"Marked attendance for {student_id}")
        return True
    except Exception as e:
        print("mark_attendance error:", e)
        return False

# Convenience function for other modules
def recognize_and_mark(img_bytes, teacher_username=None, subject=None):
    sid = recognize_face_from_bytes(img_bytes)
    if sid:
        ok = mark_attendance(sid, teacher_username, subject)
        return sid if ok else None
    return None
