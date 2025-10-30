# app.py
# Fixed: subnet validation & student access check
# Updated: only subnet prefixes are stored (e.g., "192.168.226.")

import os
import io
import time
import json
import base64
import uuid

import numpy as np
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, jsonify, session, redirect, url_for, send_file
)
from PIL import Image
import qrcode
import attendance_system

app = Flask(__name__)
app.secret_key = "attendance_secret_key"

# JSON storage
SUBNETS_FILE = "subnets.json"
SESSIONS_FILE = "active_sessions.json"

# ---------------------------------------------------
# Helper functions
# ---------------------------------------------------
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_ip(req):
    """Get the user's IP address."""
    xff = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return xff or req.remote_addr or ""


def get_subnet(ip):
    """Return the subnet prefix (e.g., 192.168.226.)"""
    parts = ip.split(".")
    return ".".join(parts[:3]) + "." if len(parts) >= 3 else ip


# ---------------------------------------------------
# Teacher Routes
# ---------------------------------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        # Load the teacher data file
        data_file = "teacher_data.json"
        if not os.path.exists(data_file):
            return render_template("login.html", error="Teacher data file missing!")

        with open(data_file, "r") as f:
            teacher_data = json.load(f)

        found = None
        dept_name = None

        for dept, teachers in teacher_data.items():
            for teacher_id, info in teachers.items():
                if info["username"] == username and info["password"] == password:
                    found = info
                    dept_name = dept
                    break
            if found:
                break

        if not found:
            return render_template("login.html", error="Invalid username or password")

        session["username"] = username
        session["teacher_name"] = found["name"]
        session["subjects"] = found.get("subjects", [])
        session["department"] = dept_name

        return redirect(url_for("home_page"))

    return render_template("login.html")


@app.route("/home")
def home_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template(
        "home.html",
        teacher_name=session.get("teacher_name"),
        department=session.get("department"),
        subjects=session.get("subjects", []),
    )


@app.route("/register_subnet", methods=["POST", "GET"])
def register_subnet():
    """
    Teacher registers hotspot subnet manually once.
    Converts full IP (like 192.168.226.166) into subnet prefix (192.168.226.)
    """
    if request.method == "GET":
        return '''
        <form method="POST">
            <label>Enter your Hotspot IP (e.g. 192.168.226.166)</label><br>
            <input name="subnet" required>
            <button type="submit">Register</button>
        </form>
        '''

    username = session.get("username", "default_teacher")
    subnet = request.form.get("subnet", "").strip()

    if not subnet:
        return "Subnet required", 400

    # 🔹 Convert full IP into subnet prefix
    parts = subnet.split(".")
    if len(parts) == 4:
        subnet = ".".join(parts[:3]) + "."

    data = load_json(SUBNETS_FILE, {})
    data[username] = {
        "name": f"{username}_hotspot",
        "subnet": subnet,
        "registered_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(SUBNETS_FILE, data)
    return f"✅ Subnet {subnet} registered successfully for {username}."


@app.route("/start_session", methods=["POST"])
def start_session():
    if "username" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 403

    teacher_username = session["username"]
    data = request.get_json(silent=True) or {}
    subject = data.get("subject")

    if not subject:
        return jsonify({"success": False, "message": "Subject is required"}), 400

    # Load teacher's registered subnet
    subnet_data = load_json(SUBNETS_FILE, {})
    teacher_info = subnet_data.get(teacher_username)

    if not teacher_info:
        return jsonify({"success": False, "message": "No registered hotspot subnet found"}), 400

    teacher_subnet = teacher_info["subnet"]
    session_id = str(uuid.uuid4())[:8]
    expiry_time = datetime.now() + timedelta(minutes=10)

    active_sessions = load_json(SESSIONS_FILE, {})
    active_sessions[session_id] = {
        "teacher": teacher_username,
        "teacher_name": session.get("teacher_name"),
        "subnet": teacher_subnet,
        "subject": subject,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expiry_time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(SESSIONS_FILE, active_sessions)

    session_link = f"{request.host_url}attendance/{session_id}"
    return jsonify({
        "success": True,
        "link": session_link,
        "expires_at": expiry_time.strftime("%H:%M:%S"),
        "subject": subject,
    })


# ---------------------------------------------------
# Student Routes
# ---------------------------------------------------
@app.route("/attendance/<session_id>")
def attendance_page(session_id):
    sessions = load_json(SESSIONS_FILE, {})
    sess = sessions.get(session_id)

    if not sess:
        return "Invalid or expired session", 404

    # Check expiry
    if datetime.strptime(sess["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
        del sessions[session_id]
        save_json(SESSIONS_FILE, sessions)
        return "Session expired", 410

    ip = get_ip(request)
    subnet = get_subnet(ip)
    teacher_subnet = sess["subnet"]

    # ✅ Safer subnet check
    if not subnet.startswith(teacher_subnet):
        return f"❌ Access denied: your IP {ip} not on teacher subnet {teacher_subnet}", 403

    return render_template("mark_attendance.html", session_id=session_id)


@app.route("/verify_face/<session_id>", methods=["POST"])
def verify_face(session_id):
    data = request.get_json()
    image_data = data.get("image")

    sessions = load_json(SESSIONS_FILE, {})
    session_info = sessions.get(session_id)
    if not session_info:
        return jsonify({"success": False, "message": "Invalid or expired session"})

    student_ip = get_ip(request)
    if not get_subnet(student_ip).startswith(session_info["subnet"]):
        return jsonify({"success": False, "message": "Access denied: not on teacher's hotspot"})

    # Decode the image
    img_data = image_data.split(",")[1]
    img_bytes = base64.b64decode(img_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    import cv2
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Recognize face
    name = attendance_system.recognize_face(img)

    if name:
        now = datetime.now().strftime("%H:%M:%S")
        return jsonify({"success": True, "name": name, "time": now})
    else:
        return jsonify({"success": False, "message": "Face not recognized"})


@app.route("/attendance_summary/<student_id>")
def attendance_summary(student_id):
    try:
        summary = attendance_system.get_attendance_summary(student_id)
        if not summary:
            return jsonify({
                "success": False,
                "message": f"No attendance record found for {student_id}"
            })
        return jsonify({
            "success": True,
            "student_id": student_id,
            "summary": summary
        })
    except Exception as e:
        print(f"[Error in attendance_summary route]: {e}")
        return jsonify({"success": False, "message": "Server error"})


# ---------------------------------------------------
# QR Code generator
# ---------------------------------------------------
@app.route("/qr/<session_id>")
def qr_code(session_id):
    sessions = load_json(SESSIONS_FILE, {})
    if session_id not in sessions:
        return "Invalid session", 404
    link = f"{request.host_url.rstrip('/')}/attendance/{session_id}"
    qr = qrcode.make(link)
    buf = io.BytesIO()
    qr.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------------------------------------------------
if __name__ == "__main__":
    attendance_system.load_encodings()
    app.run(host="0.0.0.0", port=5000, debug=True)
