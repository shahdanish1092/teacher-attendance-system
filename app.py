import face_recognition
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase_config import supabase
from datetime import datetime, timedelta
from face_recognition_helper import recognize_face_from_frame

import uuid
import os
import base64
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "default_secret")

STUDENT_IMAGES_PATH = "static/student_images"

# ====== Load known student faces ======
known_faces = []
student_ids = []

for filename in os.listdir(STUDENT_IMAGES_PATH):
    if filename.endswith(".png") or filename.endswith(".jpg"):
        path = os.path.join(STUDENT_IMAGES_PATH, filename)
        img = cv2.imread(path)
        enc = face_recognition.face_encodings(img)
        if enc:
            known_faces.append(enc[0])
            student_ids.append(os.path.splitext(filename)[0])

print(f"✅ Loaded {len(student_ids)} student faces.")


# --- Helper Functions ---

def validate_teacher(username, password):
    """Validate teacher login"""
    result = supabase.table("teachers").select("*").eq("username", username).eq("password", password).execute()
    if result.data:
        return result.data[0]
    return None


def create_session(teacher_username, subject):
    """Create active session"""
    session_id = str(uuid.uuid4())[:8]
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=30)
    supabase.table("sessions").insert({
        "session_id": session_id,
        "teacher_username": teacher_username,
        "subject": subject,
        "token": token,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires.isoformat()
    }).execute()
    return session_id, token


def get_active_sessions():
    res = supabase.table("sessions").select("*").execute()
    return res.data


# --- ROUTES ---

@app.route('/')
def home():
    return render_template("mark_attendance.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Render login form or process login"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        response = supabase.table("teachers").select("*").eq("username", username).execute()
        if response.data and response.data[0]["password"] == password:
            teacher = response.data[0]
            session["teacher_name"] = teacher["name"]
            session["teacher"] = teacher
            return redirect(url_for("dashboard"))
        else:
            return "❌ Invalid username or password"

    # For GET requests (browser visits)
    return "<h2>👩‍🏫 Teacher Login</h2><form method='POST'><input name='username' placeholder='Username'><br><input name='password' type='password' placeholder='Password'><br><button>Login</button></form>"


@app.route("/dashboard")
def dashboard():
    if "teacher_name" not in session:
        return redirect(url_for("home"))
    return f"👋 Welcome {session['teacher_name']}! Your attendance dashboard is ready."


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/start_session", methods=["POST"])
def start_session():
    if "teacher" not in session:
        return redirect(url_for("login"))

    teacher = session["teacher"]
    subject = request.form["subject"]

    session_id, token = create_session(teacher["username"], subject)

    session["current_session"] = {
        "id": session_id,
        "subject": subject,
        "token": token
    }

    return render_template("mark_attendance.html", subject=subject, session_id=session_id, teacher=teacher)


@app.route("/stop_session", methods=["POST"])
def stop_session():
    if "current_session" in session:
        current = session["current_session"]
        supabase.table("sessions").delete().eq("session_id", current["id"]).execute()
        del session["current_session"]
    return redirect(url_for("home"))


@app.route("/get_students", methods=["GET"])
def get_students():
    res = supabase.table("students").select("*").execute()
    return jsonify(res.data)


@app.route("/start_recognition")
def start_recognition():
    """Render the camera page for students."""
    if "teacher" not in session:
        return redirect(url_for("login"))
    return render_template("camera.html")  # page for students to open camera


@app.route("/stop_recognition", methods=["POST"])
def stop_recognition():
    try:
        os.system("pkill -f attendance_system.py")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/upload_face', methods=['POST'])
def upload_face():
    try:
        data = request.get_json()
        image_data = data.get("image")

        if not image_data:
            return jsonify({"message": "No image received"}), 400

        # Decode base64 image
        image_data = image_data.split(",")[1]
        img_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Convert and resize
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
                res = supabase.table("students").select("*").eq("student_id", student_id).execute()

                if res.data:
                    student = res.data[0]
                    total_attendance = int(student.get("total_attendance", 0)) + 1

                    supabase.table("students").update({
                        "total_attendance": total_attendance,
                        "last_attendance_time": datetime.now().isoformat()
                    }).eq("student_id", student_id).execute()

                    print(f"✅ Attendance marked for {student['name']} ({student_id})")

                    return jsonify({
                        "message": f"Attendance marked for {student['name']}"
                    })

        return jsonify({"message": "No recognized face found"}), 404

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"message": f"Error: {e}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)

