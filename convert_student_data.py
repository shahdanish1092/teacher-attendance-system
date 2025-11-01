import json
import csv

# Step 1: Read your student_data.json
with open("student_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Step 2: Access the nested 'students' object
students = data.get("students", {})

# Step 3: Convert to CSV
with open("students.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "student_id",
        "name",
        "year",
        "subjects",
        "image_path",
        "major",
        "starting_year",
        "total_attendance",
        "last_attendance_time"
    ])
    writer.writeheader()

    for student_id, v in students.items():
        writer.writerow({
            "student_id": v.get("student_id", student_id),
            "name": v.get("name", ""),
            "year": v.get("year", ""),
            "subjects": json.dumps(v.get("subjects", [])),  # Convert list to JSON string
            "image_path": v.get("image_path", ""),
            "major": v.get("major", ""),
            "starting_year": v.get("starting_year", ""),
            "total_attendance": v.get("total_attendance", 0),
            "last_attendance_time": v.get("last_attendance_time", None)
        })

print("✅ CSV file 'students.csv' created successfully!")
