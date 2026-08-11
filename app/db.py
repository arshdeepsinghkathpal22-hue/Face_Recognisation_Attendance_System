import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import DATE_FMT, DB_PATH, TIME_FMT


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
                class_type TEXT NOT NULL CHECK (class_type IN ('L', 'P')),
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
                class_type TEXT NOT NULL CHECK (class_type IN ('L', 'P')),
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

        # Backward-compatible migrations for existing local DBs.
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
        cursor.execute("SELECT COUNT(*) AS count FROM teacher_assignments")
        assignments_count = cursor.fetchone()["count"]
        cursor.execute("SELECT 1 FROM teacher_users WHERE teacher_id = 'admin'")
        has_demo_teacher = cursor.fetchone() is not None
        if assignments_count == 0 and has_demo_teacher:
            cursor.execute(
                """
                SELECT COALESCE(NULLIF(batch, ''), branch, 'CSE') AS batch_name
                FROM student_profile
                WHERE COALESCE(NULLIF(batch, ''), branch, '') <> ''
                ORDER BY batch_name ASC
                LIMIT 1
                """
            )
            batch_row = cursor.fetchone()
            default_batch = batch_row["batch_name"] if batch_row else "CSE"
            cursor.execute(
                """
                INSERT OR IGNORE INTO teacher_assignments(
                    teacher_id, semester_id, subject_id, batch, class_type
                )
                SELECT
                    'admin',
                    subjects.semester_id,
                    subjects.id,
                    ?,
                    CASE
                        WHEN LOWER(subjects.name) LIKE '%lab%' THEN 'P'
                        ELSE 'L'
                    END
                FROM subjects
                """
                ,
                (default_batch,),
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
    db_path: str | Path = DB_PATH,
) -> None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO teacher_users(teacher_id, name, password)
            VALUES (?, ?, ?)
            ON CONFLICT(teacher_id) DO UPDATE SET
                name = excluded.name,
                password = excluded.password
            """,
            (teacher_id, name, password),
        )
        connection.commit()


def get_teacher_user(teacher_id: str, db_path: str | Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT teacher_id, name, password
            FROM teacher_users
            WHERE teacher_id = ?
            """,
            (teacher_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


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
            if class_type not in {"L", "P"}:
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


def upsert_admin_user(
    admin_id: str,
    name: str,
    password: str,
    db_path: str | Path = DB_PATH,
) -> None:
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
            (admin_id, name, password),
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
    if normalized_type not in {"L", "P"}:
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
    if normalized_type not in {"L", "P"}:
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
    student_batch = get_student_batch(student_id=student_id, db_path=db_path).upper().strip()
    with get_connection(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                subjects.id AS subject_id,
                subjects.name AS subject_name,
                subjects.sort_order AS subject_sort_order,
                COALESCE(SUM(CASE WHEN class_sessions.class_type = 'L' THEN 1 ELSE 0 END), 0) AS held_l,
                COALESCE(SUM(CASE WHEN class_sessions.class_type = 'P' THEN 1 ELSE 0 END), 0) AS held_p,
                COALESCE(
                    SUM(
                        CASE
                            WHEN class_sessions.class_type = 'L' AND session_attendance.present = 1
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS attended_l,
                COALESCE(
                    SUM(
                        CASE
                            WHEN class_sessions.class_type = 'P' AND session_attendance.present = 1
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS attended_p
            FROM subjects
            LEFT JOIN class_sessions
                ON class_sessions.subject_id = subjects.id
                AND class_sessions.semester_id = subjects.semester_id
                AND (
                    ? = ''
                    OR class_sessions.batch IS NULL
                    OR class_sessions.batch = ''
                    OR class_sessions.batch = ?
                    OR (
                        INSTR(class_sessions.batch, ?) > 0
                        AND (
                            INSTR(class_sessions.batch, ?) + LENGTH(?) > LENGTH(class_sessions.batch)
                            OR SUBSTR(class_sessions.batch, INSTR(class_sessions.batch, ?) + LENGTH(?), 1) = 'F'
                        )
                    )
                )
            LEFT JOIN session_attendance
                ON session_attendance.session_id = class_sessions.id
                AND session_attendance.student_id = ?
            WHERE subjects.semester_id = ?
            GROUP BY subjects.id, subjects.name, subjects.sort_order
            ORDER BY subjects.sort_order ASC, subjects.name ASC
            """,
            (student_batch, student_batch, student_batch, student_batch, student_batch, student_batch, student_batch, student_id, semester_id),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
