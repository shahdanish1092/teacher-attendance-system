import json
import csv

# Step 1: Read curriculum.json
with open("curriculum.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Step 2: Prepare CSV
with open("curriculum.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "year",
        "semester",
        "current",
        "theory",
        "practicals",
        "selective"
    ])
    writer.writeheader()

    for year, year_data in data.items():
        semesters = year_data.get("Semesters", {})
        for sem_name, sem_data in semesters.items():
            writer.writerow({
                "year": year,
                "semester": sem_name,
                "current": sem_data.get("Current", False),
                "theory": json.dumps(sem_data.get("Theory", [])),
                "practicals": json.dumps(sem_data.get("Practicals", [])),
                "selective": json.dumps(sem_data.get("Selective", []))
            })

print("✅ CSV file 'curriculum.csv' created successfully!")
