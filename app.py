import os
import base64
import cv2
import numpy as np
import face_recognition
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase_config import supabase
from datetime import datetime, timedelta
from face_recognition_helper import recognize_face_from_frame

import uuid

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "default_secret")

STUDENT_IMAGES_PATH = "static/student_images"

# ====== Load known student faces (local fallback) ======
# NOTE: This is optional for server-side recognition. If you rely on ultralytics .pt model
# in face_recognition_helper.py, you can remove this block. It's kept as a fallback.
known_faces = []
student_ids = []
if os.path.isdir(STUDENT_IMAGES_PATH):
    for filename in os.listdir(STUDENT_IMAGES_PATH):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            path = os.path.join(STUDENT_IMAGES_PATH, filename)
            img = cv2.imread(path)
            enc = face_recognition.face_encodings(img)
            if enc:
                known_faces.append(enc[0])
                student_ids.append(os.path.splitext(filename)[0])
print(f"✅ Loaded {len(student_ids)} student faces (local fallback).")


# --- Helper Functions ---
def validate_teacher(username, password):
    """Validate teacher login"""
    result = supabase.table("teachers").select("*").eq("username", username).execute()
    if result.data and result.data[0].get("password") == password:
        return result.data[0]
    return None


def create_session(teacher_username, subject, duration_minutes=60):
    """Create active session and return (session_id, token, expires_at_iso, link)"""
    session_id = str(uuid.uuid4())[:8]
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=duration_minutes)
    supabase.table("sessions").insert({
        "session_id": session_id,
        "teacher_username": teacher_username,
        "subject": subject,
        "token": token,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires.isoformat()
    }).execute()
    # build public link for students (they open this on their phones)
    # note: the client will open /start_recognition?session_id=...&token=...
    # using your Render domain:
    base = os.getenv("PUBLIC_BASE_URL", "")  # set this in Render env to your public URL
    if not base:
        # fallback to relative link
        link = f"/start_recognition?session_id={session_id}&token={token}"
    else:
        link = f"{base.rstrip('/')}/start_recognition?session_id={session_id}&token={token}"
    return session_id, token, expires.isoformat(), link


def get_active_sessions():
    res = supabase.table("sessions").select("*").execute()
    return res.data or []


# --- ROUTES ---

@app.route('/')
def home():
    # show teacher control interface (home.html expects teacher data injected)
    if "teacher" in session:
        teacher = session["teacher"]
        # attempt to parse subjects field if it's a JSON/string
        subjects = teacher.get("subjects") or []
        if isinstance(subjects, str):
            try:
                import json
                subjects = json.loads(subjects)
            except Exception:
                subjects = [s.strip() for s in subjects.split(",")] if subjects else []
        department = teacher.get("department", "N/A")
        return render_template("home.html", teacher_name=teacher.get("name"), department=department, subjects=subjects)
    # not logged in -> show login page
    return render_template("login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Render login form or process login"""
    if request.method == "POST":
        username = request.form.get("username") or request.json.get("username")
        password = request.form.get("password") or request.json.get("password")

        teacher = validate_teacher(username, password)
        if teacher:
            session["teacher_name"] = teacher["name"]
            session["teacher"] = teacher
            return redirect(url_for("home"))
        else:
            # if AJAX / JSON call, return JSON
            if request.is_json:
                return jsonify({"success": False, "message": "Invalid username or password"}), 401
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "teacher_name" not in session:
        return redirect(url_for("login"))
    return f"👋 Welcome {session['teacher_name']}! Your attendance dashboard is ready."


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- start_session: accept JSON (home.html does fetch JSON) ----
@app.route("/start_session", methods=["POST"])
def start_session():
    if "teacher" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    # Accept JSON body (home.html sends JSON) or form data
    data = request.get_json(silent=True) or request.form
    subject = data.get("subject")
    if not subject:
        return jsonify({"success": False, "message": "Subject is required"}), 400

    teacher = session["teacher"]
    session_id, token, expires_iso, link = create_session(teacher["username"], subject, duration_minutes=120)

    # store current session in teacher session for convenience
    session["current_session"] = {"id": session_id, "subject": subject, "token": token}

    return jsonify({"success": True, "link": link, "session_id": session_id, "token": token, "expires_at": expires_iso})


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
    return jsonify(res.data or [])


# Students open the public link: /start_recognition?session_id=...&token=...
@app.route("/start_recognition")
def start_recognition():
    session_id = request.args.get("session_id")
    token = request.args.get("token")
    if not session_id or not token:
        return "Invalid or missing session info. Ask your teacher to share the correct link.", 400

    # validate session in DB and expiry
    res = supabase.table("sessions").select("*").eq("session_id", session_id).eq("token", token).execute()
    if not res.data:
        return "Session not found or token invalid.", 404

    sess = res.data[0]
    # check expiry
    expires_at = sess.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
        return "Session expired.", 410

    # render camera UI for students, passing session_id+token so the frontend can include them when sending images
    return render_template("camera.html", session_id=session_id, token=token)


@app.route("/stop_recognition", methods=["POST"])
def stop_recognition():
    try:
        # local-only; safe no-op on Render
        os.system("pkill -f attendance_system.py")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# upload_face: receives base64 image + session info (to validate)
@app.route('/upload_face', methods=['POST'])
def upload_face():
    try:
        payload = request.get_json()
        image_data = payload.get("image")
        session_id = payload.get("session_id") or request.args.get("session_id")
        token = payload.get("token") or request.args.get("token")

        if not image_data:
            return jsonify({"message": "No image received"}), 400

        # optional: validate session
        if session_id and token:
            s = supabase.table("sessions").select("*").eq("session_id", session_id).eq("token", token).execute()
            if not s.data:
                return jsonify({"message": "Invalid session/token"}), 403

        # Decode base64 image
        image_data = image_data.split(",")[1]
        img_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # First try server-side ultralytics helper (fast if available)
        try:
            recognized_name = recognize_face_from_frame(frame)
        except Exception as e:
            # fallback to face_recognition (embedding matching) if available
            recognized_name = None
            try:
                small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                faces = face_recognition.face_locations(rgb_small)
                encs = face_recognition.face_encodings(rgb_small, faces)

                for enc in encs:
                    if known_faces:
                        matches = face_recognition.compare_faces(known_faces, enc)
                        dists = face_recognition.face_distance(known_faces, enc)
                        idx = np.argmin(dists)
                        if matches[idx]:
                            recognized_name = student_ids[idx]
                            break
            except Exception:
                recognized_name = None

        if recognized_name:
            # Mark attendance in Supabase: try to use student_id if matches, else name
            # Prefer student_id matching
            # try student_id first
            res = supabase.table("students").select("*").eq("student_id", recognized_name).execute()
            if res.data:
                student = res.data[0]
                total_attendance = int(student.get("total_attendance", 0)) + 1
                supabase.table("students").update({
                    "total_attendance": total_attendance,
                    "last_attendance_time": datetime.utcnow().isoformat()
                }).eq("student_id", recognized_name).execute()
                return jsonify({"status": "success", "message": f"Attendance marked for {student.get('name')}"}), 200

            # else try by name field
            res2 = supabase.table("students").select("*").eq("name", recognized_name).execute()
            if res2.data:
                student = res2.data[0]
                total_attendance = int(student.get("total_attendance", 0)) + 1
                supabase.table("students").update({
                    "total_attendance": total_attendance,
                    "last_attendance_time": datetime.utcnow().isoformat()
                }).eq("student_id", student.get("student_id")).execute()
                return jsonify({"status": "success", "message": f"Attendance marked for {student.get('name')}"}), 200

            # If no student record found, still return success but note unknown
            return jsonify({"status": "success", "message": f"Recognized ({recognized_name}) — but no student record found."}), 200

        return jsonify({"status": "error", "message": "No recognized face found"}), 404

    except Exception as e:
        print("❌ Error in upload_face:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
