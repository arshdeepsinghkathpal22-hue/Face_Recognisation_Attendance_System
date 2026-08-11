import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH, ENCODINGS_PATH, STUDENTS_DIR
from app.db import initialize_db, upsert_student, upsert_student_profile
from app.face_utils import enroll_from_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enroll a student from local images.")
    parser.add_argument("--student-id", required=True, help="Unique student identifier")
    parser.add_argument("--name", required=True, help="Student full name")
    parser.add_argument(
        "--branch",
        default="CSE",
        help="Student branch (default: CSE)",
    )
    parser.add_argument(
        "--batch",
        default="",
        help="Student batch/section (default: same as branch)",
    )
    parser.add_argument(
        "--images-dir",
        help="Directory with enrollment images. Default: data/students/<student-id>",
    )
    parser.add_argument(
        "--encodings-path",
        default=str(ENCODINGS_PATH),
        help="Path to save/read known face encodings pickle",
    )
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help="SQLite database path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    images_dir = Path(args.images_dir) if args.images_dir else STUDENTS_DIR / args.student_id
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    initialize_db(args.db_path)
    valid_images = enroll_from_images(
        student_id=args.student_id,
        name=args.name,
        images_dir=images_dir,
        encodings_path=args.encodings_path,
    )
    upsert_student(args.student_id, args.name, db_path=args.db_path)
    upsert_student_profile(
        student_id=args.student_id,
        branch=args.branch,
        batch=args.batch,
        db_path=args.db_path,
    )

    print(f"Enrolled {args.student_id} - {args.name}")
    print(f"Branch: {args.branch}")
    print(f"Batch: {args.batch or args.branch}")
    print(f"Valid face images used: {valid_images}")
    print(f"Encodings file: {args.encodings_path}")


if __name__ == "__main__":
    main()
