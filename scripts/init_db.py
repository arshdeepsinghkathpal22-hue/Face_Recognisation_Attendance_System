import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH
from app.db import initialize_db


def main() -> None:
    initialize_db(DB_PATH)
    print(f"Database ready at: {DB_PATH}")


if __name__ == "__main__":
    main()
