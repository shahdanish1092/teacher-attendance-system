# app.py
import os
import io
import base64
import uuid
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file

from supabase_config import supabase
import attendance_system

# Load environment variables (optional local .env)
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", os.urandom(24))

# Initialize face encodings
attendance_system.initialize()

# ---------- Helpers ----------
def validate_teacher(username, password):
    res = supabase.table("teachers").select("*").eq("username", username).eq("password", password).execute()
    return res.data[0] if res.data else None

def create_session_record(teacher_username, subject, duration_minutes=20):
    session_id = str(uuid.uuid4())[:8]
    token = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(minutes=duration_minutes)).isoformat()
    supabase.table("sessions").insert({
        "session_id": session_id,
        "teacher_username": teacher_username,
        "subject": subject,
        "token": token,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires
    }).execute()
    return session_id, token, expires

def get_session(session_id):
    res = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
    return res.data[0] if res.data else None

# ---------- Routes ----------
@app.route("/")
def index():
    if "teacher" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        teacher = validate_teacher(username, password)
        if teacher:
            session["teacher"] = teacher
            return redirect(url_for("home"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)

@app.route("/home")
def home():
    if "teacher" not in session:
        return redirect(url_for("login"))
    teacher = session["teacher"]
    return render_template("home.html", teacher=teacher)

@app.route("/start_session", methods=["POST"])
def start_session():
    if "teacher" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 403
    teacher = session["teacher"]
    subject = request.form.get("subject")
    if not subject:
        return jsonify({"success": False, "message": "Subject required"}), 400
    session_id, token, expires = create_session_record(teacher["username"], subject)
    link = url_for("attendance_page", session_id=session_id, _external=True) + f"?token={token}"
    return render_template("session_started.html", link=link, expires=expires, subject=subject)

@app.route("/attendance/<session_id>")
def attendance_page(session_id):
    token = request.args.get("token", "")
    sess = get_session(session_id)
    if not sess:
        return "Invalid session", 404
    # expiry check
    if sess.get("expires_at") and sess["expires_at"] < datetime.utcnow().isoformat():
        return "Session expired", 410
    if sess.get("token") != token:
        return "Access denied (invalid token)", 403
    # student page
    return render_template("mark_attendance.html", session_id=session_id, token=token, subject=sess.get("subject"))

@app.route("/verify_face/<session_id>", methods=["POST"])
def verify_face(session_id):
    # client should send JSON: { "image": "data:image/jpeg;base64,...", "token": "..."}
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    token = data.get("token", "")
    image_data = data.get("image", "")
    sess = get_session(session_id)
    if not sess or sess.get("token") != token:
        return jsonify({"success": False, "message": "Invalid session/token"}), 403

    # decode base64 image
    try:
        header, b64 = image_data.split(",", 1) if "," in image_data else (None, image_data)
        img_bytes = base64.b64decode(b64)
    except Exception as e:
        return jsonify({"success": False, "message": "Bad image data"})

    student_id = attendance_system.recognize_and_mark(img_bytes, teacher_username=sess.get("teacher_username"), subject=sess.get("subject"))
    if student_id:
        return jsonify({"success": True, "student_id": student_id})
    else:
        return jsonify({"success": False, "message": "Face not recognized"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Simple attendance summary (optional)
@app.route("/attendance_summary/<student_id>")
def attendance_summary(student_id):
    res = supabase.table("attendance_logs").select("*").eq("student_id", student_id).execute()
    return jsonify(res.data)

# ---------- Run ----------
if __name__ == "__main__":
    # local dev uses port 5000; on Fly.io we'll bind to $PORT via gunicorn
    attendance_system.initialize()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
