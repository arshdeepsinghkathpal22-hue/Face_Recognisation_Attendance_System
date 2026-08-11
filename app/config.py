import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STUDENTS_DIR = DATA_DIR / "students"
MODELS_DIR = DATA_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
SEED_DIR = DATA_DIR / "seed"

DB_PATH = Path(os.getenv("ATTENDANCE_DB_PATH", str(BASE_DIR / "attendance.db")))
ENCODINGS_PATH = MODELS_DIR / "encodings.pkl"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
SESSION_SECRET = os.getenv("SESSION_SECRET", "attendance-portal-dev-secret")

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M:%S"
