# attendance_system.py
import cv2
import face_recognition
import pickle
import numpy as np
import os
from datetime import datetime
import csv
from collections import defaultdict

# ============================================================
# 🔹 Configuration
# ============================================================
ENCODING_FILE = "EncodeFile.p"  # Pre-trained encodings
known_encodings = []
student_ids = []
STUDENT_IMAGES_DIR = "static/student_images"  # Directory containing student folders
ATTENDANCE_LOG = "attendance_log.csv"         # CSV for attendance
TOLERANCE = 0.5                               # Face match tolerance


# ============================================================
# 🔹 Load Encoded Data
# ============================================================
def load_encodings():
    """
    Loads face encodings and student IDs from EncodeFile.p
    Called once when Flask starts.
    """
    global known_encodings, student_ids
    if not os.path.exists(ENCODING_FILE):
        print(f"⚠️ EncodeFile.p not found: {ENCODING_FILE}")
        return

    print("⏳ Loading face encodings...")
    with open(ENCODING_FILE, "rb") as f:
        known_encodings, student_ids = pickle.load(f)
    print(f"✅ Loaded encodings for {len(student_ids)} students.")


# ============================================================
# 🔹 Attendance Logging
# ============================================================
def mark_attendance(student_id, subject=None):
    """
    Record attendance in a CSV with timestamp and optional subject.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Create CSV if not exists
    if not os.path.exists(ATTENDANCE_LOG):
        with open(ATTENDANCE_LOG, "w") as f:
            f.write("StudentID,Date,Time,Subject\n")

    # Avoid duplicate entries
    with open(ATTENDANCE_LOG, "r+") as f:
        lines = f.readlines()
        if not any(student_id in line and date_str in line and (subject or "") in line for line in lines):
            f.write(f"{student_id},{date_str},{time_str},{subject or '-'}\n")
            print(f"🕒 Attendance marked: {student_id} ({subject or 'N/A'}) at {time_str}")
            return True

    print(f"⚠️ Duplicate attendance ignored for {student_id} ({subject or 'N/A'})")
    return False


# ============================================================
# 🔹 Face Recognition
# ============================================================
def recognize_face(image, subject=None):
    """
    Takes a BGR image from OpenCV and returns recognized student ID or None.
    Logs attendance automatically.
    """
    if not known_encodings:
        load_encodings()

    try:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

        if not face_encodings:
            print("⚠️ No face detected.")
            return None

        for encodeFace in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, encodeFace, tolerance=TOLERANCE)
            face_distances = face_recognition.face_distance(known_encodings, encodeFace)

            if True in matches:
                match_index = np.argmin(face_distances)
                student_id = student_ids[match_index]
                print(f"✅ Recognized student: {student_id}")

                mark_attendance(student_id, subject)
                return student_id

        print("❌ No known match found.")
        return None

    except Exception as e:
        print(f"[Error in recognize_face]: {e}")
        return None


# ============================================================
# 🔹 Attendance Summary
# ============================================================
def get_attendance_summary(student_id=None):
    """
    Reads attendance_log.csv and returns summary dict.
    If student_id provided → returns only that student's data.
    Example structure:
    {
        "BSCIT30": {
            "ML": {"attended": 3, "total_classes": 4, "percentage": 75.0}
        }
    }
    """
    summary = defaultdict(lambda: defaultdict(lambda: {"attended": 0, "total_classes": 0, "percentage": 0.0}))

    if not os.path.exists(ATTENDANCE_LOG):
        print("⚠️ No attendance log found.")
        return {}

    with open(ATTENDANCE_LOG, "r") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    for row in records:
        sid = row["StudentID"]
        subject = row.get("Subject", "-") or "-"
        summary[sid][subject]["attended"] += 1

    # Determine total classes = highest attendance count per subject
    totals = defaultdict(int)
    for sid, subj_data in summary.items():
        for subject, data in subj_data.items():
            totals[subject] = max(totals[subject], data["attended"])

    # Compute percentages
    for sid, subj_data in summary.items():
        for subject, data in subj_data.items():
            total_classes = totals[subject]
            attended = data["attended"]
            percentage = (attended / total_classes * 100) if total_classes else 0
            summary[sid][subject]["total_classes"] = total_classes
            summary[sid][subject]["percentage"] = round(percentage, 2)

    if student_id:
        return summary.get(student_id, {})

    return summary
