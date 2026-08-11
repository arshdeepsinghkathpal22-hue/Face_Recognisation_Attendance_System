import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH, SEED_DIR
from app.db import (
    initialize_db,
    upsert_class_session,
    upsert_admin_user,
    replace_teacher_assignments,
    upsert_semester,
    upsert_session_attendance,
    upsert_student,
    upsert_student_profile,
    upsert_subject,
    upsert_teacher_user,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed attendance portal data from JSON file.")
    parser.add_argument(
        "--file",
        default=str(SEED_DIR / "portal_seed.json"),
        help="Path to JSON data file",
    )
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH),
        help="SQLite database path",
    )
    return parser.parse_args()


def _read_json(file_path: str | Path) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _require_keys(item: dict, keys: list[str], context: str) -> None:
    missing = [key for key in keys if key not in item]
    if missing:
        raise ValueError(f"Missing keys {missing} in {context}")


def seed_data(payload: dict, db_path: str) -> None:
    initialize_db(db_path=db_path)

    students = payload.get("students", [])
    for item in students:
        _require_keys(item, ["student_id", "name", "branch"], "students")
        upsert_student(
            student_id=item["student_id"],
            name=item["name"],
            db_path=db_path,
        )
        upsert_student_profile(
            student_id=item["student_id"],
            branch=item["branch"],
            batch=item.get("batch"),
            db_path=db_path,
        )

    admins = payload.get("admins", [])
    for item in admins:
        _require_keys(item, ["admin_id", "name", "password"], "admins")
        upsert_admin_user(
            admin_id=item["admin_id"],
            name=item["name"],
            password=item["password"],
            db_path=db_path,
        )

    semesters = payload.get("semesters", [])
    for item in semesters:
        _require_keys(item, ["id", "label", "sort_order", "is_active"], "semesters")
        upsert_semester(
            semester_id=item["id"],
            label=item["label"],
            sort_order=int(item["sort_order"]),
            is_active=int(item["is_active"]),
            db_path=db_path,
        )

    subjects = payload.get("subjects", [])
    for item in subjects:
        _require_keys(item, ["id", "semester_id", "name", "sort_order"], "subjects")
        upsert_subject(
            subject_id=item["id"],
            semester_id=item["semester_id"],
            name=item["name"],
            sort_order=int(item["sort_order"]),
            db_path=db_path,
        )

    teachers = payload.get("teachers", [])
    for item in teachers:
        _require_keys(item, ["teacher_id", "name", "password"], "teachers")
        upsert_teacher_user(
            teacher_id=item["teacher_id"],
            name=item["name"],
            password=item["password"],
            db_path=db_path,
        )
        replace_teacher_assignments(
            teacher_id=item["teacher_id"],
            assignments=item.get("assignments", []),
            db_path=db_path,
        )

    class_sessions = payload.get("class_sessions", [])
    for item in class_sessions:
        _require_keys(
            item,
            ["id", "subject_id", "semester_id", "class_type", "session_date"],
            "class_sessions",
        )
        class_type = str(item["class_type"]).upper()
        if class_type not in {"L", "P"}:
            raise ValueError(f"Invalid class_type in class_sessions: {class_type}")
        upsert_class_session(
            session_id=int(item["id"]),
            subject_id=item["subject_id"],
            semester_id=item["semester_id"],
            class_type=class_type,
            session_date=item["session_date"],
            batch=item.get("batch", ""),
            start_time=item.get("start_time"),
            end_time=item.get("end_time"),
            teacher_id=item.get("teacher_id"),
            is_active=int(item.get("is_active", 0)),
            db_path=db_path,
        )

    session_attendance = payload.get("session_attendance", [])
    for item in session_attendance:
        _require_keys(item, ["session_id", "student_id", "present"], "session_attendance")
        upsert_session_attendance(
            session_id=int(item["session_id"]),
            student_id=item["student_id"],
            present=int(item["present"]),
            db_path=db_path,
        )

    print("Seed completed.")
    print(f"students: {len(students)}")
    print(f"teachers: {len(teachers)}")
    print(f"admins: {len(admins)}")
    print(f"semesters: {len(semesters)}")
    print(f"subjects: {len(subjects)}")
    print(f"class_sessions: {len(class_sessions)}")
    print(f"session_attendance: {len(session_attendance)}")


def main() -> None:
    args = parse_args()
    payload = _read_json(args.file)
    seed_data(payload=payload, db_path=args.db_path)


if __name__ == "__main__":
    main()
