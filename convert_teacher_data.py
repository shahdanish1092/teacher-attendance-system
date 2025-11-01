import json
import csv

# Step 1: Read your JSON file
with open("teacher_data.json", "r") as f:
    data = json.load(f)

# Step 2: Extract department dictionary (if nested, e.g., "IT_dept")
if "IT_dept" in data:
    data = data["IT_dept"]

# Step 3: Convert JSON to CSV
with open("teachers.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "name", "username", "password", "subjects"])
    writer.writeheader()
    for id_, v in data.items():
        writer.writerow({
            "id": id_,
            "name": v.get("name", ""),
            "username": v.get("username", ""),
            "password": v.get("password", ""),
            "subjects": json.dumps(v.get("subjects", []))  # store JSON as string
        })

print("✅ CSV file 'teachers.csv' created successfully!")
