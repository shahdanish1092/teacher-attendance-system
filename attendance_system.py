# attendance_system.py
import cv2
import face_recognition
import numpy as np
import os
from datetime import datetime
from supabase_config import supabase

STUDENT_IMAGES_PATH = "static/student_images"

# Load known faces
known_faces = []
student_ids = []

for filename in os.listdir(STUDENT_IMAGES_PATH):
    if filename.endswith(".png") or filename.endswith(".jpg"):
        img = cv2.imread(os.path.join(STUDENT_IMAGES_PATH, filename))
        enc = face_recognition.face_encodings(img)
        if enc:
            known_faces.append(enc[0])
            student_ids.append(os.path.splitext(filename)[0])

print(f"✅ Loaded {len(student_ids)} student faces")

# Webcam
cap = cv2.VideoCapture(0)
while True:
    success, frame = cap.read()
    if not success:
        break

    small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb_small)
    encs = face_recognition.face_encodings(rgb_small, faces)

    for enc, loc in zip(encs, faces):
        matches = face_recognition.compare_faces(known_faces, enc)
        face_dist = face_recognition.face_distance(known_faces, enc)
        best_match = np.argmin(face_dist)

        if matches[best_match]:
            student_id = student_ids[best_match]

            # Fetch student from Supabase
            res = supabase.table("students").select("*").eq("student_id", student_id).execute()
            if res.data:
                student = res.data[0]
                total_attendance = int(student.get("total_attendance", 0)) + 1

                supabase.table("students").update({
                    "total_attendance": total_attendance,
                    "last_attendance_time": datetime.now().isoformat()
                }).eq("student_id", student_id).execute()

                print(f"✅ Marked attendance for {student['name']} ({student_id})")

                y1, x2, y2, x1 = [v * 4 for v in loc]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, student["name"], (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    cv2.imshow("Attendance System", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
