import sqlite3
from datetime import datetime
from pathlib import Path
import re

from app.config import DATE_FMT, DB_PATH, TIME_FMT
from app.security import hash_password


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_has_column(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(column["name"] == column_name for column in columns)


def _ensure_column(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if _table_has_column(cursor, table_name, column_name):
        return
    cursor.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )


def initialize_db(db_path: str | Path = DB_PATH) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                confidence REAL,
                created_at TEXT NOT NULL,
                UNIQUE(student_id, subject, date),
                FOREIGN KEY(student_id) REFERENCES students(student_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_profile (
                student_id TEXT PRIMARY KEY,
                branch TEXT NOT NULL,
                batch TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS teacher_users (
                teacher_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                admin_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS semesters (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id TEXT PRIMARY KEY,
                semester_id TEXT NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                FOREIGN KEY(semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS class_sessions (
                id INTEGER PRIMARY KEY,
                subject_id TEXT NOT NULL,
                semester_id TEXT NOT NULL,
                class_type TEXT NOT NULL CHECK (class_type IN ('L', 'T', 'P')),
                session_date TEXT NOT NULL,
                batch TEXT NOT NULL DEFAULT '',
                start_time TEXT,
                end_time TEXT,
                teacher_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(semester_id) REFERENCES semesters(id) ON DELETE CASCADE,
                FOREIGN KEY(teacher_id) REFERENCES teacher_users(teacher_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS teacher_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT NOT NULL,
                semester_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                batch TEXT NOT NULL,
                class_type TEXT NOT NULL CHECK (class_type IN ('L', 'T', 'P')),
                UNIQUE(teacher_id, semester_id, subject_id, batch, class_type),
                FOREIGN KEY(teacher_id) REFERENCES teacher_users(teacher_id) ON DELETE CASCADE,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS session_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                present INTEGER NOT NULL CHECK (present IN (0, 1)),
                UNIQUE(session_id, student_id),
                FOREIGN KEY(session_id) REFERENCES class_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                semester_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                UNIQUE(student_id, semester_id, subject_id),
                FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            )
            """
        )

        # Backward-compatible migrations for existing local DBs.
        _ensure_column(cursor, "teacher_users", "email", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cursor, "student_profile", "batch", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cursor, "class_sessions", "batch", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cursor, "class_sessions", "start_time", "TEXT")
        _ensure_column(cursor, "class_sessions", "end_time", "TEXT")
        _ensure_column(cursor, "class_sessions", "teacher_id", "TEXT")
        _ensure_column(
            cursor,
            "class_sessions",
            "is_active",
            "INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1))",
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subjects_semester
            ON subjects(semester_id, sort_order)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_class_sessions_subject
            ON class_sessions(subject_id, semester_id, class_type)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_class_sessions_batch
            ON class_sessions(batch, semester_id, subject_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_session_attendance_student
            ON session_attendance(student_id, session_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_teacher_assignments_teacher
            ON teacher_assignments(teacher_id, semester_id, subject_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_student_subjects_student
            ON student_subjects(student_id, semester_id, subject_id)
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_teacher_users_email_unique
            ON teacher_users(LOWER(email))
            WHERE email <> ''
            """
        )
        connection.commit()


def upsert_student(
    student_id: str,
    name: str,
    db_path: str | Path = DB_PATH,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO students(student_id, name, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name = excluded.name
            """,
            (student_id, name, now),
        )
        connection.commit()


def upsert_student_profile(
    student_id: str,
    branch: str,
    batch: str | None = None,
    db_path: str | Path = DB_PATH,
) -> None:
    normalized_batch = (batch or branch).strip()
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO student_profile(student_id, branch, batch)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                branch = excluded.branch,
                batch = excluded.batch
            """,
            (student_id, branch, normalized_batch),
        )
        connection.commit()


def get_student_with_profile(
    student_id: str,
    db_path: str | Path = DB_PATH,
) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                students.student_id,
                students.name,
                COALESCE(student_profile.branch, '') AS branch,
                COALESCE(NULLIF(student_profile.batch, ''), student_profile.branch, '') AS batch
            FROM students
            LEFT JOIN student_profile
                ON student_profile.student_id = students.student_id
            WHERE students.student_id = ?
            """,
            (student_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
    return dict(row)


def list_students(db_path: str | Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                students.student_id,
                students.name,
                COALESCE(student_profile.branch, '') AS branch,
                COALESCE(NULLIF(student_profile.batch, ''), student_profile.branch, '') AS batch
            FROM students
            LEFT JOIN student_profile
                ON student_profile.student_id = students.student_id
            ORDER BY students.created_at DESC, students.student_id ASC
            """
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def list_student_ids(db_path: str | Path = DB_PATH) -> set[str]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT student_id FROM students")
        rows = cursor.fetchall()
    return {row["student_id"] for row in rows}


def get_student_batch(student_id: str, db_path: str | Path = DB_PATH) -> str:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COALESCE(NULLIF(batch, ''), branch, '') AS batch
            FROM student_profile
            WHERE student_id = ?
            """,
            (student_id,),
        )
        row = cursor.fetchone()
        return row["batch"] if row else ""


def list_students_for_batch(batch: str, db_path: str | Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                students.student_id,
                students.name
            FROM students
            JOIN student_profile ON student_profile.student_id = students.student_id
            WHERE COALESCE(NULLIF(student_profile.batch, ''), student_profile.branch, '') = ?
            ORDER BY students.name ASC
            """,
            (batch,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def is_student_in_batch(
    student_id: str,
    batch: str,
    db_path: str | Path = DB_PATH,
) -> bool:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM student_profile
            WHERE student_id = ?
                AND COALESCE(NULLIF(batch, ''), branch, '') = ?
            """,
            (student_id, batch),
        )
        return cursor.fetchone() is not None


def upsert_teacher_user(
    teacher_id: str,
    name: str,
    password: str,
    email: str = "",
    db_path: str | Path = DB_PATH,
) -> None:
    normalized_email = email.strip().lower()
    stored_password = hash_password(password)
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO teacher_users(teacher_id, name, email, password)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(teacher_id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                password = excluded.password
            """,
            (teacher_id, name, normalized_email, stored_password),
        )
        connection.commit()


def get_teacher_user(teacher_id: str, db_path: str | Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT teacher_id, name, email, password
            FROM teacher_users
            WHERE teacher_id = ?
            """,
            (teacher_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def get_teacher_user_by_login(login: str, db_path: str | Path = DB_PATH) -> dict | None:
    normalized_login = login.strip()
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT teacher_id, name, email, password
            FROM teacher_users
            WHERE teacher_id = ?
                OR LOWER(email) = LOWER(?)
            """,
            (normalized_login, normalized_login),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def list_teacher_users(db_path: str | Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT teacher_id, name, email
            FROM teacher_users
            ORDER BY name ASC, teacher_id ASC
            """
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def update_teacher_password(teacher_id: str, password: str, db_path: str | Path = DB_PATH) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE teacher_users
            SET password = ?
            WHERE teacher_id = ?
            """,
            (password, teacher_id),
        )
        connection.commit()


def replace_teacher_assignments(
    teacher_id: str,
    assignments: list[dict],
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM teacher_assignments WHERE teacher_id = ?", (teacher_id,))
        for item in assignments:
            class_type = str(item["class_type"]).upper().strip()
            if class_type not in {"L", "T", "P"}:
                raise ValueError(f"Invalid class_type: {class_type}")
            cursor.execute(
                """
                INSERT OR IGNORE INTO teacher_assignments(
                    teacher_id, semester_id, subject_id, batch, class_type
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    teacher_id,
                    item["semester_id"],
                    item["subject_id"],
                    item["batch"],
                    class_type,
                ),
            )
        connection.commit()


def upsert_teacher_assignment(
    teacher_id: str,
    semester_id: str,
    subject_id: str,
    batch: str,
    class_type: str,
    db_path: str | Path = DB_PATH,
) -> int:
    normalized_type = class_type.upper().strip()
    if normalized_type not in {"L", "T", "P"}:
        raise ValueError(f"Invalid class_type: {class_type}")
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO teacher_assignments(
                teacher_id, semester_id, subject_id, batch, class_type
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(teacher_id, semester_id, subject_id, batch, class_type)
            DO UPDATE SET batch = excluded.batch
            """,
            (teacher_id, semester_id, subject_id, batch, normalized_type),
        )
        cursor.execute(
            """
            SELECT id
            FROM teacher_assignments
            WHERE teacher_id = ?
                AND semester_id = ?
                AND subject_id = ?
                AND batch = ?
                AND class_type = ?
            """,
            (teacher_id, semester_id, subject_id, batch, normalized_type),
        )
        row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise RuntimeError("Teacher assignment save failed")
    return int(row["id"])


def update_teacher_assignment(
    assignment_id: int,
    semester_id: str,
    subject_id: str,
    batch: str,
    class_type: str,
    db_path: str | Path = DB_PATH,
) -> None:
    normalized_type = class_type.upper().strip()
    if normalized_type not in {"L", "T", "P"}:
        raise ValueError(f"Invalid class_type: {class_type}")
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE teacher_assignments
            SET semester_id = ?, subject_id = ?, batch = ?, class_type = ?
            WHERE id = ?
            """,
            (semester_id, subject_id, batch, normalized_type, assignment_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Teacher assignment not found: {assignment_id}")
        connection.commit()


def delete_teacher_assignment(
    assignment_id: int,
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM teacher_assignments WHERE id = ?", (assignment_id,))
        if cursor.rowcount == 0:
            raise KeyError(f"Teacher assignment not found: {assignment_id}")
        connection.commit()


def list_teacher_assignments(
    teacher_id: str,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                teacher_assignments.id,
                teacher_assignments.teacher_id,
                teacher_assignments.semester_id,
                semesters.label AS semester_label,
                teacher_assignments.subject_id,
                subjects.name AS subject_name,
                teacher_assignments.batch,
                teacher_assignments.class_type
            FROM teacher_assignments
            JOIN semesters ON semesters.id = teacher_assignments.semester_id
            JOIN subjects
                ON subjects.id = teacher_assignments.subject_id
                AND subjects.semester_id = teacher_assignments.semester_id
            WHERE teacher_assignments.teacher_id = ?
            ORDER BY semesters.sort_order ASC, subjects.sort_order ASC, teacher_assignments.batch ASC
            """,
            (teacher_id,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def is_teacher_assigned_to_class(
    teacher_id: str,
    semester_id: str,
    subject_id: str,
    batch: str,
    class_type: str,
    db_path: str | Path = DB_PATH,
) -> bool:
    normalized_type = class_type.upper().strip()
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM teacher_assignments
            WHERE teacher_id = ?
                AND semester_id = ?
                AND subject_id = ?
                AND batch = ?
                AND class_type = ?
            """,
            (teacher_id, semester_id, subject_id, batch, normalized_type),
        )
        return cursor.fetchone() is not None


def upsert_admin_user(
    admin_id: str,
    name: str,
    password: str,
    db_path: str | Path = DB_PATH,
) -> None:
    stored_password = hash_password(password)
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO admin_users(admin_id, name, password)
            VALUES (?, ?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                name = excluded.name,
                password = excluded.password
            """,
            (admin_id, name, stored_password),
        )
        connection.commit()


def get_admin_user(admin_id: str, db_path: str | Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT admin_id, name, password
            FROM admin_users
            WHERE admin_id = ?
            """,
            (admin_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def update_admin_password(admin_id: str, password: str, db_path: str | Path = DB_PATH) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE admin_users
            SET password = ?
            WHERE admin_id = ?
            """,
            (password, admin_id),
        )
        connection.commit()


def mark_attendance(
    student_id: str,
    subject: str,
    confidence: float | None = None,
    db_path: str | Path = DB_PATH,
    timestamp: datetime | None = None,
) -> bool:
    ts = timestamp or datetime.now()
    date_value = ts.strftime(DATE_FMT)
    time_value = ts.strftime(TIME_FMT)
    created_at = ts.isoformat(timespec="seconds")

    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO attendance(
                student_id, subject, date, time, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, subject, date_value, time_value, confidence, created_at),
        )
        connection.commit()
        return cursor.rowcount > 0


def upsert_semester(
    semester_id: str,
    label: str,
    sort_order: int,
    is_active: int,
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO semesters(id, label, sort_order, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label = excluded.label,
                sort_order = excluded.sort_order,
                is_active = excluded.is_active
            """,
            (semester_id, label, sort_order, is_active),
        )
        connection.commit()


def list_active_semesters(db_path: str | Path = DB_PATH) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, label
            FROM semesters
            WHERE is_active = 1
            ORDER BY sort_order ASC, label ASC
            """
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_semester(semester_id: str, db_path: str | Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, label FROM semesters WHERE id = ?",
            (semester_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)


def upsert_subject(
    subject_id: str,
    semester_id: str,
    name: str,
    sort_order: int,
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO subjects(id, semester_id, name, sort_order)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                semester_id = excluded.semester_id,
                name = excluded.name,
                sort_order = excluded.sort_order
            """,
            (subject_id, semester_id, name, sort_order),
        )
        connection.commit()


def list_subjects_for_semester(
    semester_id: str,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, name
            FROM subjects
            WHERE semester_id = ?
            ORDER BY sort_order ASC, name ASC
            """,
            (semester_id,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def upsert_class_session(
    session_id: int,
    subject_id: str,
    semester_id: str,
    class_type: str,
    session_date: str,
    batch: str = "",
    start_time: str | None = None,
    end_time: str | None = None,
    teacher_id: str | None = None,
    is_active: int = 0,
    db_path: str | Path = DB_PATH,
) -> None:
    normalized_type = class_type.upper()
    if normalized_type not in {"L", "T", "P"}:
        raise ValueError(f"Invalid class_type: {class_type}")
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO class_sessions(
                id, subject_id, semester_id, class_type, session_date,
                batch, start_time, end_time, teacher_id, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                subject_id = excluded.subject_id,
                semester_id = excluded.semester_id,
                class_type = excluded.class_type,
                session_date = excluded.session_date,
                batch = excluded.batch,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                teacher_id = excluded.teacher_id,
                is_active = excluded.is_active
            """,
            (
                session_id,
                subject_id,
                semester_id,
                normalized_type,
                session_date,
                batch,
                start_time,
                end_time,
                teacher_id,
                1 if is_active else 0,
            ),
        )
        connection.commit()


def create_class_session(
    subject_id: str,
    semester_id: str,
    class_type: str,
    session_date: str,
    batch: str,
    start_time: str,
    end_time: str,
    teacher_id: str,
    db_path: str | Path = DB_PATH,
) -> int:
    normalized_type = class_type.upper()
    if normalized_type not in {"L", "T", "P"}:
        raise ValueError(f"Invalid class_type: {class_type}")
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO class_sessions(
                subject_id, semester_id, class_type, session_date,
                batch, start_time, end_time, teacher_id, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                subject_id,
                semester_id,
                normalized_type,
                session_date,
                batch,
                start_time,
                end_time,
                teacher_id,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_class_session(session_id: int, db_path: str | Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                class_sessions.id,
                class_sessions.subject_id,
                class_sessions.semester_id,
                class_sessions.class_type,
                class_sessions.session_date,
                class_sessions.batch,
                class_sessions.start_time,
                class_sessions.end_time,
                class_sessions.teacher_id,
                class_sessions.is_active,
                subjects.name AS subject_name
            FROM class_sessions
            JOIN subjects ON subjects.id = class_sessions.subject_id
            WHERE class_sessions.id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def set_class_session_active(
    session_id: int,
    is_active: bool,
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE class_sessions
            SET is_active = ?
            WHERE id = ?
            """,
            (1 if is_active else 0, session_id),
        )
        connection.commit()


def upsert_session_attendance(
    session_id: int,
    student_id: str,
    present: int,
    db_path: str | Path = DB_PATH,
) -> None:
    normalized_present = 1 if int(present) else 0
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO session_attendance(session_id, student_id, present)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                present = excluded.present
            """,
            (session_id, student_id, normalized_present),
        )
        connection.commit()


def replace_student_subjects(
    student_id: str,
    subject_refs: list[dict],
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM student_subjects WHERE student_id = ?", (student_id,))
        for item in subject_refs:
            cursor.execute(
                """
                INSERT OR IGNORE INTO student_subjects(student_id, semester_id, subject_id)
                VALUES (?, ?, ?)
                """,
                (student_id, item["semester_id"], item["subject_id"]),
            )
        connection.commit()


def upsert_student_subject(
    student_id: str,
    semester_id: str,
    subject_id: str,
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO student_subjects(student_id, semester_id, subject_id)
            VALUES (?, ?, ?)
            """,
            (student_id, semester_id, subject_id),
        )
        connection.commit()


def list_student_subjects(
    student_id: str,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                student_subjects.id,
                student_subjects.student_id,
                student_subjects.semester_id,
                semesters.label AS semester_label,
                student_subjects.subject_id,
                subjects.name AS subject_name
            FROM student_subjects
            JOIN semesters ON semesters.id = student_subjects.semester_id
            JOIN subjects
                ON subjects.id = student_subjects.subject_id
                AND subjects.semester_id = student_subjects.semester_id
            WHERE student_subjects.student_id = ?
            ORDER BY semesters.sort_order ASC, subjects.sort_order ASC
            """,
            (student_id,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def is_student_registered_for_subject(
    student_id: str,
    semester_id: str,
    subject_id: str,
    db_path: str | Path = DB_PATH,
) -> bool:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM student_subjects
            WHERE student_id = ?
                AND semester_id = ?
                AND subject_id = ?
            """,
            (student_id, semester_id, subject_id),
        )
        return cursor.fetchone() is not None


def mark_session_attendance(
    session_id: int,
    student_id: str,
    db_path: str | Path = DB_PATH,
) -> dict:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, subject_id, semester_id
            FROM class_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        session = cursor.fetchone()
        if session is None:
            return {"ok": False, "inserted": False, "reason": "session_not_found"}

        cursor.execute(
            """
            SELECT 1
            FROM student_subjects
            WHERE student_id = ?
                AND semester_id = ?
                AND subject_id = ?
            """,
            (student_id, session["semester_id"], session["subject_id"]),
        )
        if cursor.fetchone() is None:
            return {
                "ok": False,
                "inserted": False,
                "reason": "subject_not_registered",
                "message": "Student is not registered for this subject.",
                "session_id": session_id,
                "student_id": student_id,
                "subject_id": session["subject_id"],
                "semester_id": session["semester_id"],
            }

        cursor.execute(
            """
            SELECT 1
            FROM session_attendance
            WHERE session_id = ?
                AND student_id = ?
                AND present = 1
            """,
            (session_id, student_id),
        )
        already_present = cursor.fetchone() is not None

        cursor.execute(
            """
            INSERT INTO session_attendance(session_id, student_id, present)
            VALUES (?, ?, 1)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                present = excluded.present
            """,
            (session_id, student_id),
        )
        cursor.execute(
            """
            SELECT present
            FROM session_attendance
            WHERE session_id = ?
                AND student_id = ?
            """,
            (session_id, student_id),
        )
        attendance_row = cursor.fetchone()
        if attendance_row is None or int(attendance_row["present"]) != 1:
            connection.rollback()
            return {
                "ok": False,
                "inserted": False,
                "reason": "attendance_write_failed",
                "session_id": session_id,
                "student_id": student_id,
            }
        connection.commit()

    return {
        "ok": True,
        "inserted": not already_present,
        "reason": "already_marked" if already_present else "attendance_marked",
        "session_id": session_id,
        "student_id": student_id,
        "subject_id": session["subject_id"],
        "semester_id": session["semester_id"],
    }


def list_present_students_for_session(
    session_id: int,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                students.student_id,
                students.name
            FROM session_attendance
            JOIN students ON students.student_id = session_attendance.student_id
            WHERE session_attendance.session_id = ?
                AND session_attendance.present = 1
            ORDER BY students.name ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def list_batches(db_path: str | Path = DB_PATH) -> list[str]:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT DISTINCT COALESCE(NULLIF(batch, ''), branch) AS batch_name
            FROM student_profile
            WHERE COALESCE(NULLIF(batch, ''), branch) <> ''
            ORDER BY batch_name ASC
            """
        )
        rows = cursor.fetchall()
    return [row["batch_name"] for row in rows]


def fetch_subject_attendance_counts(
    student_id: str,
    semester_id: str,
    db_path: str | Path = DB_PATH,
) -> list[dict]:
    student = get_student_with_profile(student_id=student_id, db_path=db_path) or {}
    student_batch = re.sub(r"\s+", "", str(student.get("batch") or "").upper())
    student_branch = re.sub(r"\s+", "", str(student.get("branch") or "").upper())
    section_match = re.search(r"F\d{1,2}", student_batch)
    student_section = section_match.group(0) if section_match else ""
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            WITH registered_subjects AS (
                SELECT
                    subjects.id AS subject_id,
                    subjects.name AS subject_name,
                    subjects.sort_order
                FROM subjects
                JOIN student_subjects
                    ON student_subjects.subject_id = subjects.id
                    AND student_subjects.semester_id = subjects.semester_id
                WHERE student_subjects.student_id = ?
                    AND subjects.semester_id = ?
            ),
            eligible_sessions AS (
                SELECT
                    class_sessions.id AS session_id,
                    class_sessions.subject_id,
                    class_sessions.class_type,
                    MAX(
                        CASE
                            WHEN session_attendance.present = 1 THEN 1
                            ELSE 0
                        END
                    ) AS student_present
                FROM class_sessions
                JOIN registered_subjects
                    ON registered_subjects.subject_id = class_sessions.subject_id
                LEFT JOIN session_attendance
                    ON session_attendance.session_id = class_sessions.id
                    AND session_attendance.student_id = ?
                WHERE class_sessions.semester_id = ?
                    AND (
                        NOT EXISTS (
                            SELECT 1
                            FROM teacher_assignments ta
                            WHERE ta.semester_id = class_sessions.semester_id
                                AND ta.subject_id = class_sessions.subject_id
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM teacher_assignments ta
                            WHERE ta.semester_id = class_sessions.semester_id
                                AND ta.subject_id = class_sessions.subject_id
                                AND (
                                    ta.batch = class_sessions.batch
                                    OR class_sessions.batch IS NULL
                                    OR class_sessions.batch = ''
                                    OR UPPER(REPLACE(ta.batch, ' ', '')) = UPPER(REPLACE(class_sessions.batch, ' ', ''))
                                    OR UPPER(REPLACE(ta.batch, ' ', '')) = ?
                                    OR UPPER(REPLACE(ta.batch, ' ', '')) = ?
                                )
                                AND (
                                    class_sessions.teacher_id IS NULL
                                    OR class_sessions.teacher_id = ''
                                    OR ta.teacher_id = class_sessions.teacher_id
                                )
                        )
                    )
                    AND (
                        ? = ''
                        OR class_sessions.batch IS NULL
                        OR class_sessions.batch = ''
                        OR UPPER(REPLACE(class_sessions.batch, ' ', '')) = ?
                        OR UPPER(REPLACE(class_sessions.batch, ' ', '')) = ?
                        OR ? LIKE UPPER(REPLACE(class_sessions.batch, ' ', '')) || '-%'
                        OR UPPER(REPLACE(class_sessions.batch, ' ', '')) LIKE ? || '-%'
                        OR (
                            ? <> ''
                            AND INSTR(UPPER(REPLACE(class_sessions.batch, ' ', '')), ?) > 0
                        )
                    )
                GROUP BY
                    class_sessions.id,
                    class_sessions.subject_id,
                    class_sessions.class_type
            )
            SELECT
                rs.subject_id,
                rs.subject_name,
                rs.sort_order AS subject_sort_order,
                COALESCE(SUM(CASE WHEN es.class_type = 'L' THEN 1 ELSE 0 END), 0) AS held_l,
                COALESCE(SUM(CASE WHEN es.class_type = 'T' THEN 1 ELSE 0 END), 0) AS held_t,
                COALESCE(SUM(CASE WHEN es.class_type = 'P' THEN 1 ELSE 0 END), 0) AS held_p,
                COALESCE(
                    SUM(
                        CASE
                            WHEN es.class_type = 'L' AND es.student_present = 1 THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS attended_l,
                COALESCE(
                    SUM(
                        CASE
                            WHEN es.class_type = 'T' AND es.student_present = 1 THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS attended_t,
                COALESCE(
                    SUM(
                        CASE
                            WHEN es.class_type = 'P' AND es.student_present = 1 THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS attended_p
            FROM registered_subjects rs
            LEFT JOIN eligible_sessions es
                ON es.subject_id = rs.subject_id
            GROUP BY rs.subject_id, rs.subject_name, rs.sort_order
            ORDER BY rs.sort_order ASC, rs.subject_name ASC
            """,
            (
                student_id,
                semester_id,
                student_id,
                semester_id,
                student_batch,
                student_branch,
                student_batch,
                student_batch,
                student_branch,
                student_batch,
                student_batch,
                student_section,
                student_section,
            ),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]

