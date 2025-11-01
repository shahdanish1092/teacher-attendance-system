
import json
import csv

# Step 1: Read the JSON file
with open("active_sessions.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Step 2: Access nested structure
sessions = data.get("active_sessions", data)

# Step 3: Convert to CSV
with open("sessions.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "session_id",
        "teacher_username",
        "subject",
        "token",
        "created_at",
        "expires_at"
    ])
    writer.writeheader()

    for key, v in sessions.items():
        writer.writerow({
            "session_id": v.get("session_id", key),
            "teacher_username": v.get("teacher_username", ""),
            "subject": v.get("subject", ""),
            "token": v.get("token", ""),
            "created_at": v.get("created_at", ""),
            "expires_at": v.get("expires_at", "")
        })

print("✅ CSV file 'sessions.csv' created successfully!")
