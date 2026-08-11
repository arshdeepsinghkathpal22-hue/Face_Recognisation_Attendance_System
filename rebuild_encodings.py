import pickle
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATA_DIR = ROOT_DIR / "data" / "students"
OUTPUT_PATH = ROOT_DIR / "data" / "models" / "encodings.pkl"
DB_PATH = ROOT_DIR / "attendance.db"


def load_face_helpers():
    print("Loading face recognition models. First load can take 30-90 seconds on Windows...", flush=True)
    from app.face_utils import enroll_from_images, load_known_faces

    return enroll_from_images, load_known_faces

def get_student_name(student_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT name FROM students WHERE student_id = ?', (student_id,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else student_id
    except Exception as e:
        return student_id

def rebuild():
    enroll_from_images, load_known_faces = load_face_helpers()

    # Remove old encodings if we want a fresh start
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    
    # Ensure encodings.pkl exists with empty content to avoid file not found
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("wb") as f:
        pickle.dump({"encodings": [], "names": [], "student_ids": []}, f)

    if not DATA_DIR.exists():
        print(f"Directory {DATA_DIR} does not exist.")
        return

    folders = sorted(path for path in DATA_DIR.iterdir() if path.is_dir())
    if not folders:
        print(f"No student folders found in: {DATA_DIR}")
        print("Add photos like: data\\students\\22BCS001\\photo1.jpg")
        print(f"Empty encodings file created at: {OUTPUT_PATH}")
        return
    
    for folder_path in folders:
        student_id = folder_path.name
        name = get_student_name(student_id)
        
        try:
            print(f"Processing student_id: {student_id} ({name})...")
            num = enroll_from_images(student_id=student_id, name=name, images_dir=folder_path, encodings_path=OUTPUT_PATH)
            print(f"  Enrolled {num} image(s).")
        except RuntimeError as e:
            print(f"Warning: {e}")
        except Exception as e:
            print(f"Error processing {student_id}: {e}")

    # Load results to print stats
    data = load_known_faces(OUTPUT_PATH)
    unique_ids = data.get("student_ids", [])
    
    print("\nFinal unique student_ids and count per ID in encodings.pkl:")
    for sid in set(unique_ids):
        count = unique_ids.count(sid)
        print(f"{sid}: {count}")

if __name__ == "__main__":
    try:
        rebuild()
    except KeyboardInterrupt:
        print("\nStopped by user. If it stopped during model loading, run again and wait for dlib to finish loading.")
        raise SystemExit(130)
