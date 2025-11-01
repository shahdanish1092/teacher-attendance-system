# train_images.py
"""
Processes images in static/student_images and (optionally) uploads them to Firebase Storage.
When using Firebase for online deployments, run this locally once to push student images.
"""

import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--upload", action="store_true", help="Upload student images to Firebase Storage (requires USE_FIREBASE)")
args = parser.parse_args()

STUDENT_IMAGES_DIR = os.path.join("static", "student_images")

if args.upload:
    # Lazy import firebase admin
    import firebase_admin
    from firebase_admin import credentials, storage
    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET")
    if not cred_path or not bucket_name:
        raise RuntimeError("Set FIREBASE_CREDENTIALS_PATH and FIREBASE_STORAGE_BUCKET to upload images.")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    bucket = storage.bucket()

    uploaded = 0
    for fname in os.listdir(STUDENT_IMAGES_DIR):
        if not fname.lower().endswith((".jpg", ".png", ".jpeg")):
            continue
        local_path = os.path.join(STUDENT_IMAGES_DIR, fname)
        blob = bucket.blob(f"student_images/{fname}")
        blob.upload_from_filename(local_path)
        uploaded += 1
    print(f"✅ Uploaded {uploaded} images to Firebase Storage in folder student_images/")
else:
    # Basic local check: list images and validate they can be read
    import cv2
    count = 0
    for fname in os.listdir(STUDENT_IMAGES_DIR):
        if fname.lower().endswith((".jpg", ".png", ".jpeg")):
            path = os.path.join(STUDENT_IMAGES_DIR, fname)
            img = cv2.imread(path)
            if img is None:
                print("⚠️ Could not read:", fname)
            else:
                count += 1
    print(f"Found {count} readable student images in {STUDENT_IMAGES_DIR}")
