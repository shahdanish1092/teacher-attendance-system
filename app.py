# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase_config import supabase
from datetime import datetime, timedelta
from face_recognition_helper import recognize_face_from_frame

import uuid
import os
import subprocess
import base64
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "default_secret")

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

@app.route("/")
def home():
    if "teacher" in session:
        return render_template("home.html", teacher=session["teacher"])
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        teacher = validate_teacher(username, password)

        if teacher:
            session["teacher"] = teacher
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

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

# For face attendance system trigger
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


@app.route("/upload_face", methods=["POST"])
def upload_face():
    try:
        data = request.get_json()
        if not data or "image" not in data:
            return jsonify({"status": "error", "message": "No image received"})

        # Decode base64 image
        img_data = data["image"].split(",")[1]
        img_bytes = base64.b64decode(img_data)
        np_img = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        # --- Run YOLO face recognition ---
        recognized_name = recognize_face_from_frame(frame)

        if recognized_name:
            # Mark attendance in Supabase
            supabase.table("attendance").insert({
                "name": recognized_name,
                "timestamp": datetime.utcnow().isoformat()
            }).execute()

            return jsonify({"status": "success", "message": f"Attendance marked for {recognized_name}!"})
        else:
            return jsonify({"status": "error", "message": "No face recognized."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
